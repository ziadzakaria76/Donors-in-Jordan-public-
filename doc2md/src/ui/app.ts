import {
  ACCEPT_ATTRIBUTE,
  convert,
  formatBytes,
  kindFor,
  MAX_FILE_BYTES,
  rejectionReason,
} from '../core/registry';
import { estimateTokens, finalize } from '../core/postprocess';
import { onLaunchFiles, takeSharedFiles } from '../core/share-target';
import { renderMarkdown } from './markdown';
import { icons } from './icons';
import { currentTheme, toggleTheme } from './theme';

type ItemStatus = 'queued' | 'converting' | 'done' | 'error' | 'cancelled';

interface QueueItem {
  id: string;
  file: File;
  status: ItemStatus;
  progress: number;
  stage: string;
  error: string;
  warnings: string[];
  markdown: string;
  /** Output was cut short; re-running with full export would produce more. */
  truncated: boolean;
  view: 'rendered' | 'raw';
  open: boolean;
}

const state = {
  items: [] as QueueItem[],
  fullExport: false,
  running: false,
  toast: '',
};

/** Aborts the conversion currently in flight, if the user asks to stop it. */
let inFlight: AbortController | null = null;

let toastTimer: number | undefined;
let nextId = 0;

const outputName = (file: File): string =>
  `${file.name.replace(/\.[^.]+$/, '') || 'document'}.md`;

// --------------------------------------------------------------------- mount

export function mountApp(root: HTMLElement): void {
  root.innerHTML = shell();
  render();

  root.addEventListener('click', onClick);
  root.addEventListener('change', onChange);

  const dropzone = must<HTMLElement>('#dropzone');
  for (const type of ['dragenter', 'dragover'] as const) {
    dropzone.addEventListener(type, (event) => {
      event.preventDefault();
      dropzone.classList.add('ring-2', 'ring-brand-500');
    });
  }
  for (const type of ['dragleave', 'drop'] as const) {
    dropzone.addEventListener(type, () => {
      dropzone.classList.remove('ring-2', 'ring-brand-500');
    });
  }
  dropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) addFiles(Array.from(files));
  });

  // Files handed over by the Android share sheet or a desktop "open with".
  void takeSharedFiles().then((files) => {
    if (files.length > 0) addFiles(files);
  });
  onLaunchFiles(addFiles);
}

function shell(): string {
  return `
    <div class="mx-auto flex min-h-dvh w-full max-w-3xl flex-col px-4 pb-32">
      <header class="flex items-center gap-3 py-4">
        <img src="icons/favicon.svg" alt="" class="size-9 rounded-lg" width="36" height="36" />
        <div class="min-w-0 flex-1">
          <h1 class="text-lg leading-tight font-semibold">Doc2MD</h1>
          <p class="truncate text-xs text-slate-500 dark:text-slate-400">
            PDF, Word &amp; Excel → Markdown, on your device
          </p>
        </div>
        <button type="button" data-action="theme" class="btn-ghost !px-3"
          aria-label="Toggle dark mode">
          <span data-slot="theme-icon">${icons.moon}</span>
        </button>
      </header>

      <section id="dropzone"
        class="card flex flex-col items-center gap-3 p-6 text-center transition">
        <input id="file-input" type="file" multiple class="sr-only"
          accept="${ACCEPT_ATTRIBUTE}" />
        <label for="file-input" class="btn-primary tappable w-full cursor-pointer sm:w-auto sm:px-8">
          ${icons.upload}<span>Choose files</span>
        </label>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          or drop them here · .pdf .docx .xlsx .xlsm .csv · up to ${formatBytes(MAX_FILE_BYTES)}
        </p>
        <label class="tappable mt-1 flex min-h-12 cursor-pointer items-center gap-3 text-sm">
          <input type="checkbox" data-action="full-export"
            class="size-5 accent-brand-600" />
          <span class="text-slate-600 dark:text-slate-300">
            Full export — never truncate long spreadsheets
          </span>
        </label>
      </section>

      <div id="batch-progress" class="hidden pt-4">
        <div class="card flex items-center gap-3 px-4 py-3">
          <div class="min-w-0 flex-1">
            <p data-slot="batch-label" class="truncate text-sm font-medium"></p>
            <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
              <div data-slot="batch-bar-fill"
                class="h-full rounded-full bg-brand-500 transition-[width]" style="width:0%"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Announced rather than shown: progress ticks would be far too chatty
           for a screen reader, so only completions are read out. -->
      <p id="queue-status" role="status" aria-live="polite" class="sr-only"></p>

      <main id="queue" class="flex flex-col gap-3 pt-4"></main>

      <footer class="mt-auto pt-8 pb-2 text-center text-xs text-slate-400 dark:text-slate-500">
        Nothing is uploaded — every conversion runs in this browser tab.
      </footer>
    </div>

    <div id="batch-bar" class="fixed inset-x-0 bottom-0 z-20 hidden
      border-t border-slate-200 bg-white/95 backdrop-blur
      dark:border-white/10 dark:bg-ink-950/95">
      <div class="mx-auto flex max-w-3xl gap-2 px-4 py-3"
        style="padding-bottom: calc(0.75rem + env(safe-area-inset-bottom))">
        <button type="button" data-action="download-zip" class="btn-primary flex-1">
          ${icons.zip}<span data-slot="zip-label">Download all</span>
        </button>
        <button type="button" data-action="clear" class="btn-secondary !px-4"
          aria-label="Clear all files">${icons.trash}</button>
      </div>
    </div>

    <div id="toast" role="status" aria-live="polite"
      class="pointer-events-none fixed inset-x-0 bottom-24 z-30 flex justify-center px-4
        opacity-0 transition-opacity"></div>
  `;
}

// -------------------------------------------------------------------- events

function onClick(event: Event): void {
  const target = (event.target as HTMLElement).closest<HTMLElement>('[data-action]');
  if (!target) return;
  const action = target.dataset['action'];
  const id = target.closest<HTMLElement>('[data-item]')?.dataset['item'];
  const item = state.items.find((candidate) => candidate.id === id);

  switch (action) {
    case 'theme': {
      toggleTheme();
      render();
      break;
    }
    case 'clear': {
      state.items = [];
      render();
      break;
    }
    case 'download-zip':
      void downloadZip();
      break;
    case 'remove':
      if (item) {
        state.items = state.items.filter((candidate) => candidate !== item);
        render();
      }
      break;
    case 'toggle-open':
      if (item) {
        item.open = !item.open;
        render();
      }
      break;
    case 'view-rendered':
    case 'view-raw':
      if (item) {
        item.view = action === 'view-raw' ? 'raw' : 'rendered';
        render();
      }
      break;
    case 'copy':
      if (item) void copyMarkdown(item);
      break;
    case 'download':
      if (item) downloadMarkdown(item);
      break;
    case 'share':
      if (item) void shareMarkdown(item);
      break;
    case 'retry':
      if (item) {
        item.status = 'queued';
        item.error = '';
        render();
        void runQueue();
      }
      break;
    case 'convert-in-full': {
      state.fullExport = true;
      const toggle = document.querySelector<HTMLInputElement>('[data-action="full-export"]');
      if (toggle) toggle.checked = true;
      reconvertTruncated();
      break;
    }
    case 'stop':
      // Only the in-flight conversion has a controller; a queued item is
      // simply dropped back out of the queue.
      if (item?.status === 'converting') inFlight?.abort();
      else if (item) {
        item.status = 'cancelled';
        render();
      }
      break;
  }
}

function onChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  if (target.id === 'file-input') {
    if (target.files && target.files.length > 0) addFiles(Array.from(target.files));
    // Reset so picking the same file twice still fires a change event.
    target.value = '';
    return;
  }
  if (target.dataset['action'] === 'full-export') {
    state.fullExport = target.checked;
    if (state.fullExport) reconvertTruncated();
  }
}

/**
 * Turning full export on re-runs the files it would change. Without this the
 * truncation warning tells the user to flip a switch that does nothing to the
 * file they are looking at.
 */
function reconvertTruncated(): void {
  const affected = state.items.filter((item) => item.status === 'done' && item.truncated);
  if (affected.length === 0) return;
  for (const item of affected) {
    item.status = 'queued';
    item.warnings = [];
    item.truncated = false;
  }
  showToast(`Re-converting ${affected.length} file${affected.length === 1 ? '' : 's'} in full`);
  void runQueue();
}

// --------------------------------------------------------------------- queue

function addFiles(files: File[]): void {
  for (const file of files) {
    const reason = rejectionReason(file);
    state.items.push({
      id: `f${nextId++}`,
      file,
      status: reason ? 'error' : 'queued',
      progress: 0,
      stage: '',
      error: reason ?? '',
      warnings: [],
      markdown: '',
      truncated: false,
      view: 'rendered',
      open: false,
    });
  }
  render();
  void runQueue();
}

/**
 * Converts one file at a time. Phones are memory-constrained and a 50 MB PDF
 * alongside a 40 MB workbook is a good way to get the tab killed; sequential
 * also keeps the progress display honest.
 */
async function runQueue(): Promise<void> {
  if (state.running) return;
  state.running = true;
  try {
    for (;;) {
      const item = state.items.find((candidate) => candidate.status === 'queued');
      if (!item) break;
      item.status = 'converting';
      item.progress = 0;
      item.stage = 'Reading';
      item.error = '';
      inFlight = new AbortController();
      render();
      try {
        const result = await convert(item.file, {
          fullExport: state.fullExport,
          signal: inFlight.signal,
          onProgress: (fraction, stage) => {
            item.progress = Math.min(1, Math.max(0, fraction));
            if (stage) item.stage = stage;
            renderItem(item);
          },
        });
        item.markdown = finalize({
          filename: item.file.name,
          kind: kindFor(item.file),
          markdown: result.markdown,
          meta: result.meta,
        });
        item.warnings = result.meta.warnings;
        item.truncated = result.meta.truncated ?? false;
        item.status = 'done';
        item.progress = 1;
        item.open = state.items.length === 1;
      } catch (error) {
        // One bad file must never take the rest of the batch down with it —
        // and a file the user stopped is not a failure.
        if (error instanceof DOMException && error.name === 'AbortError') {
          item.status = 'cancelled';
        } else {
          item.status = 'error';
          item.error = error instanceof Error ? error.message : String(error);
        }
      } finally {
        inFlight = null;
      }
      render();
    }
  } finally {
    state.running = false;
  }
}

// -------------------------------------------------------------------- render

function render(): void {
  must<HTMLElement>('[data-slot="theme-icon"]').innerHTML =
    currentTheme() === 'dark' ? icons.sun : icons.moon;

  const queue = must<HTMLElement>('#queue');
  queue.innerHTML = state.items.map(itemCard).join('');

  const done = state.items.filter((item) => item.status === 'done');
  const bar = must<HTMLElement>('#batch-bar');
  bar.classList.toggle('hidden', done.length < 2);
  must<HTMLElement>('[data-slot="zip-label"]').textContent =
    `Download all ${done.length} as .zip`;

  renderBatchProgress(done.length);

  const toast = must<HTMLElement>('#toast');
  toast.innerHTML = state.toast
    ? `<span class="rounded-full bg-slate-900 px-4 py-2 text-sm text-white shadow-lg
        dark:bg-white dark:text-slate-900">${escape(state.toast)}</span>`
    : '';
  toast.classList.toggle('opacity-0', !state.toast);
}

/**
 * With several files queued, per-card progress does not answer "how far through
 * the batch am I". This strip does, and it doubles as the screen-reader
 * announcement — but only on completions, since progress ticks several times a
 * second would make the page unusable with a reader on.
 */
function renderBatchProgress(doneCount: number): void {
  const pending = state.items.filter(
    (item) => item.status === 'queued' || item.status === 'converting',
  );
  const strip = must<HTMLElement>('#batch-progress');
  const total = state.items.filter((item) => item.status !== 'error').length;

  strip.classList.toggle('hidden', pending.length === 0 || total < 2);
  if (pending.length > 0 && total >= 2) {
    const current = state.items.find((item) => item.status === 'converting');
    const position = total - pending.length + 1;
    must<HTMLElement>('[data-slot="batch-label"]').textContent = current
      ? `Converting ${position} of ${total} · ${current.file.name}`
      : `Queued ${pending.length} of ${total}`;
    must<HTMLElement>('[data-slot="batch-bar-fill"]').style.width =
      `${Math.round(((total - pending.length) / total) * 100)}%`;
  }

  const status = must<HTMLElement>('#queue-status');
  const next =
    state.items.length === 0
      ? ''
      : pending.length === 0
        ? `${doneCount} of ${state.items.length} converted.`
        : `Converting. ${doneCount} of ${state.items.length} done.`;
  // Rewriting identical text makes some readers announce it twice.
  if (status.textContent !== next) status.textContent = next;
}

/** Cheap in-place update for progress ticks, which fire far too often to re-render on. */
function renderItem(item: QueueItem): void {
  const node = document.querySelector<HTMLElement>(`[data-item="${item.id}"]`);
  if (!node) return;
  const bar = node.querySelector<HTMLElement>('[data-slot="bar"]');
  if (bar) bar.style.width = `${Math.round(item.progress * 100)}%`;
  const stage = node.querySelector<HTMLElement>('[data-slot="stage"]');
  if (stage) {
    stage.textContent = item.stage
      ? `${item.stage}… ${Math.round(item.progress * 100)}%`
      : 'Converting…';
  }
}

function itemCard(item: QueueItem): string {
  const tokens = item.markdown ? estimateTokens(item.markdown) : 0;
  return `
    <article class="card overflow-hidden" data-item="${item.id}">
      <div class="flex items-start gap-3 p-4">
        <span class="mt-0.5 text-slate-400">${icons.file}</span>
        <div class="min-w-0 flex-1">
          <p class="truncate font-medium">${escape(item.file.name)}</p>
          <p class="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            ${formatBytes(item.file.size)}${
              item.status === 'done'
                ? ` · ~${tokens.toLocaleString()} tokens`
                : ''
            }
          </p>
        </div>
        ${statusChip(item)}
        <button type="button" data-action="remove"
          class="btn-ghost !px-2 text-slate-400"
          aria-label="Remove ${escape(item.file.name)}">${icons.x}</button>
      </div>

      ${
        item.status === 'converting'
          ? `<div class="px-4 pb-4">
               <div class="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-white/10"
                 role="progressbar" aria-valuemin="0" aria-valuemax="100"
                 aria-valuenow="${Math.round(item.progress * 100)}"
                 aria-label="Converting ${escape(item.file.name)}">
                 <div data-slot="bar" class="h-full rounded-full bg-brand-500 transition-[width]"
                   style="width:${Math.round(item.progress * 100)}%"></div>
               </div>
               <div class="mt-2 flex items-center gap-2">
                 <p data-slot="stage" class="flex-1 text-xs text-slate-500 dark:text-slate-400">
                   ${item.stage ? `${escape(item.stage)}… ${Math.round(item.progress * 100)}%` : 'Converting…'}
                 </p>
                 <button type="button" data-action="stop" class="btn-ghost text-sm">Stop</button>
               </div>
             </div>`
          : ''
      }

      ${
        item.status === 'error'
          ? `<div class="mx-4 mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700
               dark:bg-rose-500/10 dark:text-rose-300">
               <p>${escape(item.error)}</p>
               ${
                 // Retrying only makes sense for a file we could in principle
                 // read; an .xls will still be an .xls next time.
                 rejectionReason(item.file) === null
                   ? `<button type="button" data-action="retry"
                        class="btn-ghost mt-1 !px-2 text-rose-700 dark:text-rose-300">
                        Try again
                      </button>`
                   : ''
               }
             </div>`
          : ''
      }

      ${
        item.status === 'cancelled'
          ? `<div class="mx-4 mb-4 flex items-center gap-2 rounded-xl bg-slate-100 p-3 text-sm
               text-slate-600 dark:bg-white/5 dark:text-slate-300">
               <span class="flex-1">Stopped before it finished.</span>
               <button type="button" data-action="retry" class="btn-ghost !px-3 text-sm">
                 Convert again
               </button>
             </div>`
          : ''
      }

      ${item.status === 'done' ? resultBody(item) : ''}
    </article>
  `;
}

function resultBody(item: QueueItem): string {
  const warnings = item.warnings.length
    ? `<div class="mx-4 mb-3 rounded-xl bg-amber-50 p-3 text-xs text-amber-800
         dark:bg-amber-400/10 dark:text-amber-200">
         <ul class="space-y-1">
           ${item.warnings.map((warning) => `<li>${escape(warning)}</li>`).join('')}
         </ul>
         ${
           // The toggle lives at the top of the page. On a phone with several
           // files queued that is a long scroll away from the warning that
           // names it, so offer it here too.
           item.truncated
             ? `<button type="button" data-action="convert-in-full"
                  class="btn-ghost mt-1 !px-2 text-xs text-amber-900 dark:text-amber-100">
                  Convert this in full
                </button>`
             : ''
         }
       </div>`
    : '';

  const preview = item.open
    ? `<div class="border-t border-slate-200 dark:border-white/10">
         <div class="flex gap-1 p-2">
           <button type="button" data-action="view-rendered"
             class="${item.view === 'rendered' ? 'btn-secondary' : 'btn-ghost'} flex-1 text-sm">
             ${icons.eye}<span>Preview</span>
           </button>
           <button type="button" data-action="view-raw"
             class="${item.view === 'raw' ? 'btn-secondary' : 'btn-ghost'} flex-1 text-sm">
             ${icons.code}<span>Markdown</span>
           </button>
         </div>
         <div class="max-h-[60vh] overflow-auto px-4 pb-4">
           ${
             item.view === 'raw'
               ? `<pre class="md-source text-xs leading-relaxed whitespace-pre-wrap break-words">${escape(item.markdown)}</pre>`
               : `<div class="md-preview">${renderMarkdown(item.markdown)}</div>`
           }
         </div>
       </div>`
    : '';

  return `
    ${warnings}
    <div class="flex flex-wrap gap-2 px-4 pb-4">
      <button type="button" data-action="copy" class="btn-secondary flex-1">
        ${icons.copy}<span>Copy</span>
      </button>
      <button type="button" data-action="download" class="btn-secondary flex-1">
        ${icons.download}<span>.md</span>
      </button>
      ${
        canShareFiles()
          ? `<button type="button" data-action="share" class="btn-secondary flex-1">
               ${icons.share}<span>Share</span>
             </button>`
          : ''
      }
    </div>
    <button type="button" data-action="toggle-open"
      class="btn-ghost w-full !rounded-none border-t border-slate-200 text-sm
        dark:border-white/10">
      ${item.open ? 'Hide output' : 'Show output'}
    </button>
    ${preview}
  `;
}

function statusChip(item: QueueItem): string {
  switch (item.status) {
    case 'queued':
      return `<span class="chip bg-slate-200 text-slate-600 dark:bg-white/10 dark:text-slate-300">Queued</span>`;
    case 'converting':
      return `<span class="chip bg-brand-500/15 text-brand-600 dark:text-brand-400">Working</span>`;
    case 'done':
      return `<span class="chip bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">${icons.check}</span>`;
    case 'error':
      return `<span class="chip bg-rose-500/15 text-rose-700 dark:text-rose-300">${icons.alert}</span>`;
    case 'cancelled':
      return `<span class="chip bg-slate-200 text-slate-600 dark:bg-white/10 dark:text-slate-300">Stopped</span>`;
  }
}

// ------------------------------------------------------------------- outputs

function markdownFile(item: QueueItem): File {
  return new File([item.markdown], outputName(item.file), {
    type: 'text/markdown',
  });
}

async function copyMarkdown(item: QueueItem): Promise<void> {
  try {
    await navigator.clipboard.writeText(item.markdown);
    showToast('Markdown copied');
  } catch {
    // Clipboard API needs a secure context and, on some Android builds, a
    // fresh user gesture. Fall back to a selection the user can copy.
    const area = document.createElement('textarea');
    area.value = item.markdown;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    showToast(ok ? 'Markdown copied' : 'Could not copy — use Download instead');
  }
}

function downloadMarkdown(item: QueueItem): void {
  saveBlob(markdownFile(item), outputName(item.file));
}

function canShareFiles(): boolean {
  return typeof navigator.canShare === 'function' && typeof navigator.share === 'function';
}

async function shareMarkdown(item: QueueItem): Promise<void> {
  const file = markdownFile(item);
  try {
    if (navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: outputName(item.file) });
      return;
    }
    await navigator.share({ title: outputName(item.file), text: item.markdown });
  } catch (error) {
    // A user dismissing the share sheet is an AbortError, not a failure.
    if (error instanceof DOMException && error.name === 'AbortError') return;
    showToast('Sharing is not available here — use Download');
  }
}

async function downloadZip(): Promise<void> {
  const done = state.items.filter((item) => item.status === 'done');
  if (done.length === 0) return;
  showToast('Building .zip…');

  const { zipSync, strToU8 } = await import('fflate');
  const entries: Record<string, Uint8Array> = {};
  const used = new Set<string>();
  for (const item of done) {
    let name = outputName(item.file);
    // Two sheets called "report.xlsx" from different folders must not collide.
    for (let n = 2; used.has(name); n++) {
      name = outputName(item.file).replace(/\.md$/, `-${n}.md`);
    }
    used.add(name);
    entries[name] = strToU8(item.markdown);
  }
  const zipped = zipSync(entries, { level: 6 });
  const blob = new Blob([zipped as BlobPart], { type: 'application/zip' });
  saveBlob(blob, `doc2md-${done.length}-files.zip`);
  showToast('');
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  // Revoking immediately can cancel the download on some Android builds.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

// -------------------------------------------------------------------- helpers

function showToast(message: string): void {
  state.toast = message;
  render();
  window.clearTimeout(toastTimer);
  if (!message) return;
  toastTimer = window.setTimeout(() => {
    state.toast = '';
    render();
  }, 2600);
}

function escape(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function must<T extends Element>(selector: string): T {
  const node = document.querySelector<T>(selector);
  if (!node) throw new Error(`Missing element: ${selector}`);
  return node;
}
