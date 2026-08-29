/**
 * Turning a rectangular grid of text into a GitHub-flavoured Markdown table.
 * Shared by every converter — spreadsheets, Word tables and PDF column
 * detection all end up here.
 */

export type Grid = string[][];
export type Align = 'left' | 'right';

/** How far down a sheet to look for the real header row. */
const HEADER_SEARCH_DEPTH = 8;

/** Rows below the candidate that are sampled to see whether data follows it. */
const HEADER_LOOKAHEAD = 5;

/** C0 control characters other than the whitespace handled above, plus DEL. */
const CONTROL_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;

/**
 * Latin and Arabic-Indic digits, with the usual decorations: sign, currency,
 * thousands separators, percent, and accounting parentheses.
 */
const NUMERIC =
  /^[-+(]?\s*[$€£¥₪﷼]?\s*[\d٠-٩۰-۹][\d٠-٩۰-۹,٬ ]*(?:[.٫][\d٠-٩۰-۹]+)?\s*[%)]?$/;

const SCIENTIFIC = /^[-+]?\d+(?:\.\d+)?[eE][-+]?\d+$/;

export function looksNumeric(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed === '') return false;
  return NUMERIC.test(trimmed) || SCIENTIFIC.test(trimmed);
}

/** True for a cell holding nothing but whitespace. */
export function isBlank(cell: string): boolean {
  return cell.trim() === '';
}

/**
 * A table cell cannot contain a raw newline or an unescaped pipe without
 * breaking the table, so both are neutralised here rather than at render time.
 *
 * Leading whitespace is kept. Renderers collapse it, but a spreadsheet that
 * indents an outline column is using it to carry the nesting, and the model
 * reading the raw Markdown is the audience that matters.
 */
export function escapeCell(value: string): string {
  const indent = (/^[ \t]+/.exec(value)?.[0] ?? '').replace(/\t/g, '    ');
  const body = value
    .slice(/^[ \t]+/.exec(value)?.[0].length ?? 0)
    .replace(/\r\n?|\n/g, '<br>')
    .replace(/\t/g, ' ')
    .replace(/\|/g, '\\|')
    .replace(CONTROL_CHARS, '')
    .replace(/ {2,}/g, ' ')
    .trimEnd();
  return body === '' ? '' : indent + body;
}

/**
 * Squares the grid off and drops every fully-empty row and column. Spreadsheets
 * are full of spacer rows and columns that carry no information but would cost
 * a pipe pair each in the output.
 */
export function normalizeGrid(grid: Grid): Grid {
  const width = grid.reduce((max, row) => Math.max(max, row.length), 0);
  if (width === 0) return [];

  // Trailing whitespace is noise. Leading whitespace is not — see escapeCell.
  const padded = grid.map((row) =>
    Array.from({ length: width }, (_, column) => (row[column] ?? '').trimEnd()),
  );
  const rows = padded.filter((row) => !row.every(isBlank));
  if (rows.length === 0) return [];

  const keptColumns: number[] = [];
  for (let column = 0; column < width; column++) {
    if (rows.some((row) => !isBlank(row[column] ?? ''))) keptColumns.push(column);
  }
  return rows.map((row) => keptColumns.map((column) => row[column] ?? ''));
}

/**
 * Finds the row that actually labels the columns. Real spreadsheets open with
 * a title, a date, a blank line and only then the header, so taking row 0 on
 * faith produces a table whose header is "Q3 Budget Review" and whose first
 * data row is the real header.
 *
 * The winning row is the one that is well filled, mostly non-numeric, free of
 * repeated labels, and followed by rows that are themselves well filled.
 * Expects an already-normalised grid.
 */
export function detectHeaderRow(grid: Grid): number {
  if (grid.length <= 1) return 0;
  const width = grid[0]?.length ?? 0;
  if (width === 0) return 0;

  let best = 0;
  let bestScore = -Infinity;
  const depth = Math.min(HEADER_SEARCH_DEPTH, grid.length - 1);

  for (let index = 0; index < depth; index++) {
    const row = grid[index]!;
    const filled = row.filter((cell) => !isBlank(cell)).map((cell) => cell.trim());
    if (filled.length === 0) continue;

    const fill = filled.length / width;
    const textiness = filled.filter((cell) => !looksNumeric(cell)).length / filled.length;
    const distinct = new Set(filled).size / filled.length;
    const following = grid.slice(index + 1, index + 1 + HEADER_LOOKAHEAD);
    const below =
      following.length === 0
        ? 0
        : following.reduce(
            (sum, next) => sum + next.filter((cell) => !isBlank(cell)).length / width,
            0,
          ) / following.length;

    // Weights: being wide matters most, then reading like labels rather than
    // data, then having data underneath. Ties go to the earlier row.
    const score = fill * 1.5 + textiness + distinct * 0.5 + below;
    if (score > bestScore) {
      bestScore = score;
      best = index;
    }
  }
  return best;
}

/** Right-aligns columns that are predominantly numeric. Costs one character. */
export function inferAlignments(rows: Grid, width: number): Align[] {
  return Array.from({ length: width }, (_, column) => {
    const values = rows.map((row) => row[column] ?? '').filter((value) => !isBlank(value));
    if (values.length === 0) return 'left';
    return values.filter(looksNumeric).length / values.length >= 0.6 ? 'right' : 'left';
  });
}

export function renderTable(header: string[], rows: Grid, aligns: Align[]): string {
  const width = header.length;
  const line = (cells: string[]): string =>
    `| ${Array.from({ length: width }, (_, i) => escapeCell(cells[i] ?? '')).join(' | ')} |`;
  const rule = `| ${Array.from({ length: width }, (_, i) =>
    aligns[i] === 'right' ? '---:' : '---',
  ).join(' | ')} |`;
  return [line(header), rule, ...rows.map(line)].join('\n');
}
