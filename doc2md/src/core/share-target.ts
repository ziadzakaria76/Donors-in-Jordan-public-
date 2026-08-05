import {
  SHARE_CACHE,
  SHARE_PARAM,
  shareFileKey,
  shareIndexKey,
  type SharedIndex,
} from './share-target-constants';

/**
 * Redeems the claim ticket the service worker left in the URL after an Android
 * "Share → Doc2MD", returning the shared files and clearing them from the
 * cache. Returns an empty list for an ordinary visit.
 */
export async function takeSharedFiles(): Promise<File[]> {
  const url = new URL(window.location.href);
  const id = url.searchParams.get(SHARE_PARAM);
  if (!id) return [];

  // Drop the ticket immediately so a refresh does not re-open a stale share.
  url.searchParams.delete(SHARE_PARAM);
  window.history.replaceState({}, '', url.pathname + url.search + url.hash);

  if (!('caches' in window)) return [];
  const cache = await caches.open(SHARE_CACHE);
  const indexResponse = await cache.match(shareIndexKey(id));
  if (!indexResponse) return [];

  const index = (await indexResponse.json()) as SharedIndex;
  const files: File[] = [];
  for (let i = 0; i < index.files.length; i++) {
    const entry = index.files[i]!;
    const key = shareFileKey(id, i);
    const response = await cache.match(key);
    if (!response) continue;
    const blob = await response.blob();
    files.push(new File([blob], entry.name, { type: entry.type || blob.type }));
    await cache.delete(key);
  }
  await cache.delete(shareIndexKey(id));
  return files;
}

/**
 * Desktop/ChromeOS "open with" handoff. Harmless where unsupported — the
 * property simply is not there.
 */
export function onLaunchFiles(handler: (files: File[]) => void): void {
  const queue = (window as unknown as { launchQueue?: LaunchQueue }).launchQueue;
  if (!queue?.setConsumer) return;
  queue.setConsumer((params) => {
    void Promise.all(params.files.map((handle) => handle.getFile())).then((files) => {
      if (files.length > 0) handler(files);
    });
  });
}

interface LaunchQueue {
  setConsumer(consumer: (params: { files: { getFile(): Promise<File> }[] }) => void): void;
}
