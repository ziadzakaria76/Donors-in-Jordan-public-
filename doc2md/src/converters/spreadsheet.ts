import type { CellObject, WorkSheet } from 'xlsx';
import {
  detectHeaderRow,
  inferAlignments,
  isBlank,
  normalizeGrid,
  renderTable,
  type Grid,
} from '../core/gfm-table';
import { extensionOf } from '../core/registry';
import { ConversionError, type ConversionResult, type ConvertOptions, type Converter } from '../core/types';
import { parseDelimited } from './delimited';

/** Sheets longer than this are cut down unless the user asked for everything. */
const TRUNCATE_ABOVE = 500;
const TRUNCATE_TO = 100;

export const convert: Converter = async (file, options) => {
  return extensionOf(file.name) === 'csv'
    ? convertDelimited(file, options)
    : convertWorkbook(file, options);
};

// ------------------------------------------------------------------ workbook

async function convertWorkbook(
  file: File,
  options: ConvertOptions,
): Promise<ConversionResult> {
  options.onProgress?.(0, 'Reading workbook');
  const XLSX = await import('xlsx');
  const bytes = new Uint8Array(await file.arrayBuffer());

  let workbook;
  try {
    workbook = XLSX.read(bytes, {
      type: 'array',
      // Dates as Date objects, and number formats retained, so `format_cell`
      // can reproduce what Excel displayed rather than a raw serial.
      cellDates: true,
      cellNF: true,
    });
  } catch (error) {
    throw new ConversionError(
      'Could not read this workbook — it may be password-protected or corrupt.',
      { cause: error },
    );
  }

  const names = workbook.SheetNames;
  if (names.length === 0) throw new ConversionError('This workbook has no sheets.');

  const warnings: string[] = [];
  const sections: string[] = [`# ${baseName(file.name)}`];
  let truncated = false;

  for (const [index, name] of names.entries()) {
    options.signal?.throwIfAborted();
    options.onProgress?.(index / names.length, `Sheet ${index + 1} of ${names.length}`);
    const sheet = workbook.Sheets[name];
    sections.push(`## Sheet: ${name}`);
    const body = sheet
      ? renderGrid(sheetToGrid(XLSX, sheet), options, warnings, `Sheet "${name}"`, () => {
          truncated = true;
        })
      : '';
    sections.push(body || '<!-- empty sheet -->');
  }

  options.onProgress?.(1, 'Done');
  return {
    markdown: sections.join('\n\n'),
    meta: { sheets: names, warnings, truncated },
  };
}

type XlsxModule = typeof import('xlsx');

/**
 * Reads the sheet cell by cell rather than through `sheet_to_json`. That gives
 * exact control over the origin (a sheet whose used range starts at C5 must
 * still line its merges up), and it keeps every value a string — the library's
 * object-building path is the one carrying the prototype-pollution advisory.
 */
function sheetToGrid(XLSX: XlsxModule, sheet: WorkSheet): Grid {
  const ref = sheet['!ref'];
  if (!ref) return [];
  const range = XLSX.utils.decode_range(ref);

  const rows: Grid = [];
  for (let r = range.s.r; r <= range.e.r; r++) {
    const row: string[] = [];
    for (let c = range.s.c; c <= range.e.c; c++) {
      const cell = sheet[XLSX.utils.encode_cell({ r, c })] as CellObject | undefined;
      row.push(cell ? cellText(XLSX, cell) : '');
    }
    rows.push(row);
  }

  // A merged range stores its value only in the top-left cell, so a table built
  // from it has a labelled first row and blanks underneath. Repeating the value
  // down the range keeps every data row self-describing, which is the whole
  // point of handing this to a model.
  for (const merge of sheet['!merges'] ?? []) {
    const anchor = rows[merge.s.r - range.s.r]?.[merge.s.c - range.s.c] ?? '';
    if (anchor === '') continue;
    for (let r = merge.s.r; r <= merge.e.r; r++) {
      const row = rows[r - range.s.r];
      if (!row) continue;
      for (let c = merge.s.c; c <= merge.e.c; c++) {
        const column = c - range.s.c;
        if (column >= 0 && column < row.length) row[column] = anchor;
      }
    }
  }
  return rows;
}

/** The cell as Excel displayed it: formula results, formatted numbers and dates. */
function cellText(XLSX: XlsxModule, cell: CellObject): string {
  if (cell.t === 'z' || cell.v === undefined || cell.v === null) return '';
  try {
    // Covers error cells too, which format as #DIV/0! and friends — more
    // faithful than blanking a cell the author can see has gone wrong.
    const formatted = XLSX.utils.format_cell(cell);
    if (typeof formatted === 'string') return formatted;
  } catch {
    // Fall through: a broken number format should not lose the value.
  }
  if (cell.v instanceof Date) return cell.v.toISOString().slice(0, 10);
  if (typeof cell.v === 'boolean') return cell.v ? 'TRUE' : 'FALSE';
  return String(cell.v);
}

// ----------------------------------------------------------------- delimited

async function convertDelimited(
  file: File,
  options: ConvertOptions,
): Promise<ConversionResult> {
  options.onProgress?.(0, 'Reading');
  const grid = parseDelimited(await file.text());
  const warnings: string[] = [];
  let truncated = false;
  const body = renderGrid(grid, options, warnings, 'This file', () => {
    truncated = true;
  });
  options.onProgress?.(1, 'Done');

  return {
    // No "## Sheet:" heading here — the file is the sheet, and naming it twice
    // would just cost tokens.
    markdown: [`# ${baseName(file.name)}`, body || '<!-- no rows -->'].join('\n\n'),
    meta: { sheets: [baseName(file.name)], warnings, truncated },
  };
}

// -------------------------------------------------------------------- shared

function renderGrid(
  raw: Grid,
  options: ConvertOptions,
  warnings: string[],
  label: string,
  onTruncated?: () => void,
): string {
  const grid = normalizeGrid(raw);
  if (grid.length === 0) return '';

  const headerIndex = detectHeaderRow(grid);
  const header = grid[headerIndex]!;

  // Anything above the header is a title, a date stamp, a note. Keep it, above
  // the table, in document order — dropping it would lose real content.
  const preamble = grid
    .slice(0, headerIndex)
    .map((row) =>
      row
        .filter((cell) => !isBlank(cell))
        .map((cell) => cell.trim())
        .join(' · '),
    )
    .filter((line) => line !== '');

  let body = grid.slice(headerIndex + 1);
  const total = body.length;
  const parts = [...preamble];

  if (!options.fullExport && total > TRUNCATE_ABOVE) {
    body = body.slice(0, TRUNCATE_TO);
    parts.push(renderTable(header, body, inferAlignments(body, header.length)));
    parts.push(
      `<!-- truncated: ${total} rows total, showing the first ${TRUNCATE_TO} -->`,
    );
    warnings.push(
      `${label}: showing ${TRUNCATE_TO} of ${total} rows. Turn on "Full export" to include them all.`,
    );
    onTruncated?.();
    return parts.join('\n\n');
  }

  parts.push(renderTable(header, body, inferAlignments(body, header.length)));
  return parts.join('\n\n');
}

function baseName(filename: string): string {
  return filename.replace(/\.[^.]+$/, '') || 'document';
}
