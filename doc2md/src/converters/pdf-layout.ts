/**
 * Turning positioned glyph runs back into document structure.
 *
 * A PDF has no paragraphs, no headings and no tables — only text placed at
 * coordinates. Everything here is geometry: which runs share a baseline, which
 * baselines belong to the same paragraph, which font sizes stand above the body
 * text, and which columns line up often enough to be a table. Kept free of
 * pdf.js so it can be tested against synthetic layouts.
 */

import { inferAlignments, renderTable, type Grid } from '../core/gfm-table';

/** One positioned run of text, straight from the page. */
export interface Piece {
  text: string;
  x: number;
  y: number;
  width: number;
  /** Font size in points, not the bounding-box height. */
  size: number;
  rtl: boolean;
}

/** A run of text sharing a horizontal band, split into gap-separated cells. */
export interface Line {
  text: string;
  segments: Segment[];
  x: number;
  right: number;
  y: number;
  size: number;
  rtl: boolean;
}

export interface Segment {
  text: string;
  x: number;
  right: number;
}

export interface PageLayout {
  number: number;
  width: number;
  height: number;
  lines: Line[];
}

// Two runs share a baseline if their y values differ by less than this
// fraction of the font size — enough for subscripts and mixed sizes.
const BASELINE_TOLERANCE = 0.5;
/** A gap this many times the font size starts a new word. */
const WORD_GAP = 0.18;
/**
 * A gap this many times the font size is column spacing rather than a word
 * space. Justified prose can stretch a space to roughly half an em, so the
 * threshold sits well clear of that.
 */
const COLUMN_GAP = 1.2;
/** Font sizes are rounded to this before being compared. */
const SIZE_QUANTUM = 0.25;
/** A size must exceed the body text by this much to count as a heading. */
const HEADING_RATIO = 1.08;
/** A heading is a short line; anything longer is a styled paragraph. */
const MAX_HEADING_CHARS = 160;

const BULLET = /^[•▪◦‣·∙*—–-]\s+/;
const ORDERED = /^(\d{1,3}|[a-z]|[ivxlcdm]{1,5})[.)]\s+/i;
/** Indentation, in points, that counts as one nesting level. */
const INDENT_STEP = 18;

/**
 * Lines further apart than this multiple of the font size start a new
 * paragraph, however the previous line ended. Without it, a page with few
 * lines gives a poor right-margin estimate and unrelated lines get glued
 * together.
 */
const PARAGRAPH_LEADING = 2;

/** Punctuation that can plausibly end a paragraph. */
const TERMINAL = /[.!?:;\u061F\u06D4]["')\]]?\s*$/;

// ---------------------------------------------------------------- line build

/**
 * Groups pieces into lines. Runs are bucketed by baseline, then ordered along
 * the line — right to left where the line is right-to-left, so that Arabic
 * comes out in logical order rather than reversed.
 */
export function buildLines(pieces: Piece[]): Line[] {
  const meaningful = pieces.filter((piece) => piece.text !== '');
  if (meaningful.length === 0) return [];

  const buckets: Piece[][] = [];
  for (const piece of [...meaningful].sort((a, b) => b.y - a.y)) {
    const bucket = buckets[buckets.length - 1];
    const reference = bucket?.[0];
    if (bucket && reference && Math.abs(reference.y - piece.y) <= reference.size * BASELINE_TOLERANCE) {
      bucket.push(piece);
    } else {
      buckets.push([piece]);
    }
  }

  return buckets.map(assembleLine).filter((line) => line.text !== '');
}

function assembleLine(bucket: Piece[]): Line {
  const rtl = bucket.filter((piece) => piece.rtl).length * 2 > bucket.length;
  // Visual order is left-to-right; logical order for an RTL line is the
  // reverse. Reordering whole runs is not the same as reversing a string —
  // each run's characters stay exactly as the PDF reported them.
  const ordered = [...bucket].sort((a, b) => (rtl ? b.x - a.x : a.x - b.x));
  const size = dominantSize(bucket);

  const segments: Segment[] = [];
  let current: Segment | null = null;
  let previous: Piece | null = null;

  for (const piece of ordered) {
    if (piece.text.trim() === '') {
      // pdf.js represents a gap between runs as a single space whose *width*
      // spans the whole gap, so a column boundary looks like an ordinary space
      // unless the width is checked. This is the main signal that a line is a
      // table row rather than a sentence.
      if (piece.width > size * COLUMN_GAP) current = null;
      else if (current) current.text += ' ';
      previous = piece;
      continue;
    }
    const gap = previous ? gapBetween(previous, piece, rtl) : 0;
    if (!current || (previous && gap > size * COLUMN_GAP)) {
      current = { text: piece.text, x: piece.x, right: piece.x + piece.width };
      segments.push(current);
    } else {
      if (gap > size * WORD_GAP && !/\s$/.test(current.text)) current.text += ' ';
      current.text += piece.text;
      current.x = Math.min(current.x, piece.x);
      current.right = Math.max(current.right, piece.x + piece.width);
    }
    previous = piece;
  }

  for (const segment of segments) segment.text = segment.text.replace(/\s+/g, ' ').trim();
  const kept = segments.filter((segment) => segment.text !== '');

  const xs = bucket.map((piece) => piece.x);
  const rights = bucket.map((piece) => piece.x + piece.width);
  return {
    text: kept.map((segment) => segment.text).join(' ').trim(),
    segments: kept,
    x: Math.min(...xs),
    right: Math.max(...rights),
    y: bucket[0]!.y,
    size,
    rtl,
  };
}

/** Distance between two runs along the reading direction. */
function gapBetween(previous: Piece, next: Piece, rtl: boolean): number {
  return rtl ? previous.x - (next.x + next.width) : next.x - (previous.x + previous.width);
}

/** The size covering the most characters, so one large drop-cap cannot win. */
function dominantSize(pieces: Piece[]): number {
  const weights = new Map<number, number>();
  for (const piece of pieces) {
    const size = quantise(piece.size);
    weights.set(size, (weights.get(size) ?? 0) + piece.text.trim().length);
  }
  let best = quantise(pieces[0]!.size);
  let bestWeight = -1;
  for (const [size, weight] of weights) {
    if (weight > bestWeight || (weight === bestWeight && size > best)) {
      best = size;
      bestWeight = weight;
    }
  }
  return best;
}

function quantise(size: number): number {
  return Math.round(size / SIZE_QUANTUM) * SIZE_QUANTUM;
}

// -------------------------------------------------------------- font scaling

export interface HeadingScale {
  body: number;
  /** Distinct heading sizes, largest first; index + 1 is the heading level. */
  levels: number[];
}

/**
 * Works out which font size is body text and which sizes are headings.
 *
 * Ranking the distinct larger sizes beats fixed ratios: a document whose
 * headings are 13/12/11pt over 10pt body gets a clean h1/h2/h3 rather than
 * three h3s, and one with a single 30pt title does not get an h1 for every
 * slightly-emphasised line.
 */
export function headingScale(pages: PageLayout[], furniture = new Set<string>()): HeadingScale {
  const weights = new Map<number, number>();
  for (const page of pages) {
    for (const line of page.lines) {
      // Running heads and feet are set small and repeat on every page, so
      // counting them can make 8pt furniture look like the body text and
      // promote the actual body to a heading.
      if (isFurniture(line, page, furniture)) continue;
      weights.set(line.size, (weights.get(line.size) ?? 0) + line.text.length);
    }
  }
  if (weights.size === 0) return { body: 0, levels: [] };

  let body = 0;
  let bestWeight = -1;
  for (const [size, weight] of weights) {
    if (weight > bestWeight) {
      bestWeight = weight;
      body = size;
    }
  }

  const levels = [...weights.keys()]
    .filter((size) => size >= body * HEADING_RATIO)
    .sort((a, b) => b - a)
    .slice(0, 6);
  return { body, levels };
}

export function headingLevel(line: Line, scale: HeadingScale): number | null {
  if (line.text.length > MAX_HEADING_CHARS) return null;
  const index = scale.levels.indexOf(line.size);
  return index === -1 ? null : index + 1;
}

// ----------------------------------------------------------------- furniture

/** Fraction of the page height treated as header/footer margin. */
const BAND = 0.12;
/** A line must repeat on this share of pages to be furniture. */
const REPEAT_RATIO = 0.6;
/** Below this many pages, "repeats on most pages" means nothing. */
const MIN_PAGES_FOR_REPEATS = 3;

const PAGE_NUMBER = /^(page\s*)?[\divxlcdm]+(\s*(of|\/|-)\s*[\divxlcdm]+)?$/i;

/** Digits vary between pages; the shape of the line does not. */
export function furnitureKey(text: string): string {
  return text.toLowerCase().replace(/\d+/g, '#').replace(/\s+/g, ' ').trim();
}

export function inBand(line: Line, pageHeight: number): boolean {
  return line.y >= pageHeight * (1 - BAND) || line.y <= pageHeight * BAND;
}

/**
 * Finds running heads and feet: lines sitting in the top or bottom margin whose
 * shape repeats across most pages. Bare page numbers go regardless — they are
 * furniture even in a two-page document.
 */
export function findFurniture(pages: PageLayout[]): Set<string> {
  const counts = new Map<string, number>();
  for (const page of pages) {
    const seen = new Set<string>();
    for (const line of page.lines) {
      if (!inBand(line, page.height)) continue;
      seen.add(furnitureKey(line.text));
    }
    for (const key of seen) counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  const furniture = new Set<string>();
  if (pages.length >= MIN_PAGES_FOR_REPEATS) {
    const threshold = pages.length * REPEAT_RATIO;
    for (const [key, count] of counts) {
      if (count >= threshold && key !== '') furniture.add(key);
    }
  }
  return furniture;
}

export function isFurniture(line: Line, page: PageLayout, furniture: Set<string>): boolean {
  if (!inBand(line, page.height)) return false;
  const key = furnitureKey(line.text);
  return furniture.has(key) || PAGE_NUMBER.test(line.text.trim());
}

// --------------------------------------------------------------------- table

/** A table needs at least this many rows before columns mean anything. */
const MIN_TABLE_ROWS = 3;
/** Column positions this close together, relative to page width, are the same column. */
const COLUMN_TOLERANCE = 0.025;

interface TableRegion {
  start: number;
  end: number;
  grid: Grid;
}

/**
 * Finds runs of lines whose gap-separated segments land in the same columns.
 *
 * Deliberately strict: three rows minimum, at least two columns, consistent
 * segment counts, and every segment must map to a distinct column. Anything
 * ambiguous stays plain text, which loses formatting but never invents a table
 * that was not there.
 */
export function findTables(lines: Line[], pageWidth: number): TableRegion[] {
  const regions: TableRegion[] = [];
  const tolerance = pageWidth * COLUMN_TOLERANCE;
  let index = 0;

  while (index < lines.length) {
    if ((lines[index]?.segments.length ?? 0) < 2) {
      index++;
      continue;
    }
    let end = index;
    while (end + 1 < lines.length && (lines[end + 1]?.segments.length ?? 0) >= 2) end++;

    const run = lines.slice(index, end + 1);
    if (run.length >= MIN_TABLE_ROWS) {
      const grid = gridFor(run, tolerance);
      if (grid) regions.push({ start: index, end, grid });
    }
    index = end + 1;
  }
  return regions;
}

function gridFor(run: Line[], tolerance: number): Grid | null {
  const columns = clusterColumns(run, tolerance);
  if (columns.length < 2) return null;

  const grid: Grid = [];
  for (const line of run) {
    const row = new Array<string>(columns.length).fill('');
    for (const segment of line.segments) {
      const column = nearestColumn(columns, segment.x, tolerance);
      // A segment that matches no column, or a column already taken, means the
      // run is not really tabular.
      if (column === -1 || row[column] !== '') return null;
      row[column] = segment.text;
    }
    grid.push(row);
  }

  // Require most cells to be filled; a sparse grid is usually prose that
  // happened to have a wide gap in it.
  const filled = grid.flat().filter((cell) => cell !== '').length;
  if (filled < grid.length * columns.length * 0.6) return null;
  return grid;
}

function clusterColumns(run: Line[], tolerance: number): number[] {
  const starts = run
    .flatMap((line) => line.segments.map((segment) => segment.x))
    .sort((a, b) => a - b);
  const clusters: number[][] = [];
  for (const start of starts) {
    const last = clusters[clusters.length - 1];
    if (last && start - last[0]! <= tolerance) last.push(start);
    else clusters.push([start]);
  }
  // A real column appears on most rows.
  return clusters
    .filter((cluster) => cluster.length >= Math.ceil(run.length * 0.6))
    .map((cluster) => cluster.reduce((sum, value) => sum + value, 0) / cluster.length);
}

function nearestColumn(columns: number[], x: number, tolerance: number): number {
  let best = -1;
  let bestDistance = tolerance;
  for (const [index, column] of columns.entries()) {
    const distance = Math.abs(column - x);
    if (distance <= bestDistance) {
      bestDistance = distance;
      best = index;
    }
  }
  return best;
}

// -------------------------------------------------------------------- blocks

export type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'listItem'; ordered: boolean; level: number; text: string }
  | { kind: 'table'; grid: Grid }
  | { kind: 'note'; text: string };

/**
 * Rebuilds one page's blocks. Wrapped lines are rejoined into paragraphs; a
 * line only continues the previous one if the previous reached the right
 * margin, which is what distinguishes a wrap from a deliberate short line.
 */
export function pageBlocks(page: PageLayout, scale: HeadingScale, furniture: Set<string>): Block[] {
  const lines = page.lines.filter((line) => !isFurniture(line, page, furniture));
  if (lines.length === 0) return [];

  const tables = findTables(lines, page.width);
  const inTable = new Map<number, TableRegion>();
  for (const region of tables) {
    for (let i = region.start; i <= region.end; i++) inTable.set(i, region);
  }

  // The right margin: most body lines stop just short of it, and a wrapped
  // line is one that reaches it.
  const rights = lines.map((line) => line.right).sort((a, b) => a - b);
  const margin = rights[Math.floor(rights.length * 0.9)] ?? page.width;
  const leftmost = Math.min(...lines.map((line) => line.x));

  const blocks: Block[] = [];
  let paragraph: { text: string; wrapped: boolean } | null = null;
  let previousLine: Line | null = null;

  const flush = (): void => {
    if (paragraph && paragraph.text.trim() !== '') {
      blocks.push({ kind: 'paragraph', text: paragraph.text.trim() });
    }
    paragraph = null;
  };

  for (let index = 0; index < lines.length; index++) {
    const region = inTable.get(index);
    if (region) {
      if (region.start === index) {
        flush();
        blocks.push({ kind: 'table', grid: region.grid });
      }
      continue;
    }

    const line = lines[index]!;
    const level = headingLevel(line, scale);
    if (level !== null) {
      flush();
      blocks.push({ kind: 'heading', level, text: line.text });
      previousLine = line;
      continue;
    }

    const bullet = BULLET.exec(line.text);
    const ordered = bullet ? null : ORDERED.exec(line.text);
    if (bullet || ordered) {
      flush();
      const marker = (bullet ?? ordered)![0];
      blocks.push({
        kind: 'listItem',
        ordered: ordered !== null,
        level: Math.min(5, Math.max(0, Math.round((line.x - leftmost) / INDENT_STEP))),
        text: line.text.slice(marker.length).trim(),
      });
      previousLine = line;
      continue;
    }

    // A list item's continuation line is indented under its marker.
    const previous = blocks[blocks.length - 1];
    if (
      paragraph === null &&
      previous?.kind === 'listItem' &&
      line.x > leftmost + INDENT_STEP / 2 &&
      !/[.!?:;]$/.test(previous.text)
    ) {
      previous.text = `${previous.text} ${line.text}`.trim();
      previousLine = line;
      continue;
    }

    const leading = previousLine ? previousLine.y - line.y : 0;
    // A continuation sits at or left of the line above it. A line starting
    // further right is a first-line indent, which begins a new paragraph.
    const continues =
      previousLine !== null &&
      leading <= line.size * PARAGRAPH_LEADING &&
      line.x <= previousLine.x + line.size;
    if (paragraph?.wrapped && continues) paragraph.text += ` ${line.text}`;
    else {
      flush();
      paragraph = { text: line.text, wrapped: true };
    }
    // Reaching the right margin means the line ran out of room. Ragged-right
    // text often stops a word or two short, so an unfinished sentence counts
    // as a wrap too; a line that both stops short and ends a sentence is the
    // one the author meant to end.
    paragraph.wrapped = line.right >= margin - line.size || !TERMINAL.test(line.text);
    previousLine = line;
  }

  flush();
  return blocks;
}

export function blocksToMarkdown(blocks: Block[]): string {
  const parts: string[] = [];
  let pendingList: string[] = [];

  const flushList = (): void => {
    if (pendingList.length > 0) parts.push(pendingList.join('\n'));
    pendingList = [];
  };

  let ordinal = 0;
  let ordered: boolean | null = null;
  for (const block of blocks) {
    // A switch between bullets and numbers ends one list and starts another;
    // run together, the two would be one ambiguous list.
    if (block.kind !== 'listItem' || (ordered !== null && block.ordered !== ordered)) {
      flushList();
      ordinal = 0;
      ordered = null;
    }
    switch (block.kind) {
      case 'heading':
        parts.push(`${'#'.repeat(Math.min(6, block.level))} ${block.text}`);
        break;
      case 'paragraph':
        parts.push(block.text);
        break;
      case 'listItem': {
        ordered = block.ordered;
        const indent = '  '.repeat(block.level);
        const marker = block.ordered ? `${++ordinal}. ` : '- ';
        pendingList.push(`${indent}${marker}${block.text}`);
        break;
      }
      case 'table': {
        const header = block.grid[0]!;
        const body = block.grid.slice(1);
        parts.push(renderTable(header, body, inferAlignments(body, header.length)));
        break;
      }
      case 'note':
        parts.push(block.text);
        break;
    }
  }
  flushList();
  return parts.join('\n\n');
}
