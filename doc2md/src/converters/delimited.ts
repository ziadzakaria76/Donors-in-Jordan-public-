/**
 * An RFC 4180 reader for CSV and its relatives.
 *
 * Deliberately not routed through SheetJS: for a delimited file the text *is*
 * the displayed value, so parsing it directly is strictly more faithful than
 * letting a spreadsheet engine coerce `007` to 7 or reformat `2026-08-04`
 * according to a locale.
 */

/** Semicolons are the norm wherever the comma is a decimal separator. */
const CANDIDATES = [',', ';', '\t', '|'] as const;

/** Enough of the file to tell the delimiter apart; the rest cannot disagree much. */
const SNIFF_BYTES = 8192;

function countOutsideQuotes(text: string, delimiter: string): number {
  let inQuotes = false;
  let count = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (inQuotes && text[i + 1] === '"') i++;
      else inQuotes = !inQuotes;
    } else if (!inQuotes && char === delimiter) {
      count++;
    }
  }
  return count;
}

export function detectDelimiter(text: string): string {
  const sample = text.slice(0, SNIFF_BYTES);
  let best = ',';
  let bestCount = 0;
  for (const candidate of CANDIDATES) {
    const count = countOutsideQuotes(sample, candidate);
    if (count > bestCount) {
      bestCount = count;
      best = candidate;
    }
  }
  return best;
}

/**
 * Handles quoted fields, doubled quotes, embedded newlines and either line
 * ending. A quote only opens a field at the field's start, which is what
 * spreadsheet exporters produce and what keeps stray quotes inside unquoted
 * text from swallowing the rest of the file.
 */
export function parseDelimited(text: string, delimiter?: string): string[][] {
  const source = text.replace(/^\uFEFF/, '');
  const delim = delimiter ?? detectDelimiter(source);

  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let inQuotes = false;

  const endField = (): void => {
    row.push(field);
    field = '';
  };
  const endRow = (): void => {
    endField();
    rows.push(row);
    row = [];
  };

  for (let i = 0; i < source.length; i++) {
    const char = source[i]!;

    if (inQuotes) {
      if (char !== '"') {
        field += char;
      } else if (source[i + 1] === '"') {
        field += '"';
        i++;
      } else {
        inQuotes = false;
      }
      continue;
    }

    if (char === '"' && field === '') {
      inQuotes = true;
    } else if (char === delim) {
      endField();
    } else if (char === '\r') {
      if (source[i + 1] === '\n') i++;
      endRow();
    } else if (char === '\n') {
      endRow();
    } else {
      field += char;
    }
  }

  // A trailing newline ends the last row cleanly and must not add an empty one.
  if (field !== '' || row.length > 0) endRow();
  return rows;
}
