/// <reference lib="webworker" />
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import {
  SHARE_CACHE,
  SHARE_PARAM,
  shareFileKey,
  shareIndexKey,
  type SharedIndex,
} from './core/share-target-constants';

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

/** Shared payloads older than this are swept on activate. */
const SHARE_TTL_MS = 60 * 60 * 1000;

self.addEventListener('message', (event) => {
  if ((event.data as { type?: string } | undefined)?.type === 'SKIP_WAITING') {
    void self.skipWaiting();
  }
});

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Everything runs client-side, so any in-scope navigation can be served by the
// cached shell — that is what makes the app work offline.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL(`${self.registration.scope}index.html`), {
    denylist: [/\/share-target$/],
  }),
);

/**
 * Android's share sheet POSTs the files here. There is no server, so the
 * worker stashes them in the cache and redirects to the app with a claim
 * ticket, which the page redeems on load.
 */
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'POST') return;
  const url = new URL(request.url);
  if (!url.pathname.endsWith('/share-target')) return;
  event.respondWith(receiveShare(request, url));
});

async function receiveShare(request: Request, url: URL): Promise<Response> {
  const appRoot = url.pathname.replace(/share-target$/, '');
  let id = '';
  try {
    const form = await request.formData();
    const files = form.getAll('files').filter((v): v is File => v instanceof File);
    if (files.length > 0) {
      id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
      const cache = await caches.open(SHARE_CACHE);
      const index: SharedIndex = { createdAt: Date.now(), files: [] };
      for (let i = 0; i < files.length; i++) {
        const file = files[i]!;
        index.files.push({ name: file.name || `shared-${i + 1}`, type: file.type });
        await cache.put(
          shareFileKey(id, i),
          new Response(file, {
            headers: { 'content-type': file.type || 'application/octet-stream' },
          }),
        );
      }
      await cache.put(
        shareIndexKey(id),
        new Response(JSON.stringify(index), {
          headers: { 'content-type': 'application/json' },
        }),
      );
    }
  } catch {
    // Fall through to a plain redirect: better to open the app empty than to
    // show the share sheet an error page.
  }
  const target = id ? `${appRoot}?${SHARE_PARAM}=${encodeURIComponent(id)}` : appRoot;
  return Response.redirect(target, 303);
}

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      await sweepStaleShares();
      await self.clients.claim();
    })(),
  );
});

async function sweepStaleShares(): Promise<void> {
  if (!(await caches.has(SHARE_CACHE))) return;
  const cache = await caches.open(SHARE_CACHE);
  const cutoff = Date.now() - SHARE_TTL_MS;
  const stale = new Set<string>();
  for (const request of await cache.keys()) {
    if (!request.url.endsWith('/index.json')) continue;
    const body = (await (await cache.match(request))?.json()) as SharedIndex | undefined;
    if (!body || body.createdAt < cutoff) {
      stale.add(request.url.slice(0, request.url.lastIndexOf('/') + 1));
    }
  }
  if (stale.size === 0) return;
  for (const request of await cache.keys()) {
    for (const prefix of stale) {
      if (request.url.startsWith(prefix)) await cache.delete(request);
    }
  }
}
