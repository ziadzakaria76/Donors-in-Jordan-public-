/**
 * Shared between the page and the service worker, so keep it free of anything
 * that needs DOM or WebWorker globals.
 */
export const SHARE_CACHE = 'doc2md-share-v1';

/** Query parameter the service worker redirects back to the app with. */
export const SHARE_PARAM = 'shared';

/**
 * Cache keys live under a synthetic path that no real request can collide
 * with. `index` holds the file list; the rest hold the bytes.
 */
export function shareIndexKey(id: string): string {
  return `https://doc2md.invalid/share/${encodeURIComponent(id)}/index.json`;
}

export function shareFileKey(id: string, position: number): string {
  return `https://doc2md.invalid/share/${encodeURIComponent(id)}/${position}`;
}

export interface SharedIndex {
  createdAt: number;
  files: { name: string; type: string }[];
}
