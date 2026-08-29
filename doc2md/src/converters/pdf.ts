import { ConversionError, type Converter } from '../core/types';
import {
  blocksToMarkdown,
  buildLines,
  findFurniture,
  headingScale,
  pageBlocks,
  type PageLayout,
  type Piece,
} from './pdf-layout';

/**
 * pdf.js hands back positioned glyph runs; everything structural is inferred in
 * ./pdf-layout. This module is only the driver: load, walk pages, collect
 * pieces, and note the pages that have no text to collect.
 */
export const convert: Converter = async (file, options) => {
  options.onProgress?.(0.02, 'Loading PDF');
  const pdfjs = await import('pdfjs-dist');
  await configureWorker(pdfjs);

  const bytes = new Uint8Array(await file.arrayBuffer());
  let document;
  try {
    document = await pdfjs.getDocument({
      data: bytes,
      // No network at runtime, by design: a PDF referencing a standard font
      // must not send the browser off to fetch it.
      useSystemFonts: false,
    }).promise;
  } catch (error) {
    throw new ConversionError(
      'Could not read this PDF — it may be password-protected or corrupt.',
      { cause: error },
    );
  }

  const warnings: string[] = [];
  const pages: PageLayout[] = [];
  const emptyPages: number[] = [];

  try {
    for (let number = 1; number <= document.numPages; number++) {
      options.onProgress?.(
        0.05 + (0.75 * (number - 1)) / document.numPages,
        `Page ${number} of ${document.numPages}`,
      );
      options.signal?.throwIfAborted();
      const page = await document.getPage(number);
      try {
        const viewport = page.getViewport({ scale: 1 });
        const content = await page.getTextContent();
        const pieces = content.items.flatMap(toPiece);
        const lines = buildLines(pieces);
        if (lines.length === 0) emptyPages.push(number);
        pages.push({ number, width: viewport.width, height: viewport.height, lines });
      } finally {
        page.cleanup();
      }
    }
  } finally {
    await document.destroy();
  }

  options.onProgress?.(0.85, 'Rebuilding layout');
  const furniture = findFurniture(pages);
  const scale = headingScale(pages, furniture);

  const sections: string[] = [];
  for (const page of pages) {
    if (page.lines.length === 0) {
      // Never silently drop a page. A scanned one is exactly the case where a
      // reader would otherwise never know content was missing.
      sections.push(`<!-- page ${page.number}: no text layer, OCR needed -->`);
      continue;
    }
    const markdown = blocksToMarkdown(pageBlocks(page, scale, furniture));
    if (markdown.trim() !== '') sections.push(markdown);
  }

  if (emptyPages.length > 0) {
    warnings.push(
      emptyPages.length === document.numPages
        ? 'No page in this PDF has a text layer — it is a scan and needs OCR.'
        : `${emptyPages.length} page(s) have no text layer and need OCR: ${summarise(emptyPages)}.`,
    );
  }
  if (furniture.size > 0) {
    warnings.push(
      `Removed ${furniture.size} repeating header/footer line(s) found on most pages.`,
    );
  }

  options.onProgress?.(1, 'Done');
  return {
    markdown: sections.join('\n\n'),
    meta: { pages: document.numPages, warnings },
  };
};

type PdfjsModule = typeof import('pdfjs-dist');

/**
 * The browser needs an explicit worker URL; Vite emits the worker as an asset
 * and rewrites this. Under Node the tests resolve pdf.js to its legacy build,
 * which runs on a fake worker in-process and must not be pointed at a URL.
 */
async function configureWorker(pdfjs: PdfjsModule): Promise<void> {
  if (typeof window === 'undefined' || pdfjs.GlobalWorkerOptions.workerSrc) return;
  const worker = await import('pdfjs-dist/build/pdf.worker.mjs?url');
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
}

/** A text item's font size, taken from the transform rather than the box height. */
function toPiece(item: unknown): Piece[] {
  const candidate = item as {
    str?: string;
    dir?: string;
    width?: number;
    height?: number;
    transform?: number[];
  };
  if (typeof candidate.str !== 'string' || candidate.transform === undefined) return [];

  const transform = candidate.transform;
  const scaleY = Math.hypot(transform[2] ?? 0, transform[3] ?? 0);
  const size = scaleY > 0 ? scaleY : (candidate.height ?? 10);
  return [
    {
      text: candidate.str,
      x: transform[4] ?? 0,
      y: transform[5] ?? 0,
      width: candidate.width ?? 0,
      size,
      rtl: candidate.dir === 'rtl',
    },
  ];
}

/** "2, 5–7" rather than a wall of numbers. */
function summarise(numbers: number[]): string {
  const ranges: string[] = [];
  let start = numbers[0]!;
  let previous = start;
  for (const value of numbers.slice(1)) {
    if (value === previous + 1) {
      previous = value;
      continue;
    }
    ranges.push(start === previous ? `${start}` : `${start}–${previous}`);
    start = value;
    previous = value;
  }
  ranges.push(start === previous ? `${start}` : `${start}–${previous}`);
  return ranges.join(', ');
}
