/**
 * Fixtures are built in code rather than committed as binaries, so a reviewer
 * can see exactly what goes in and what the snapshot is asserting about.
 */
import * as XLSX from 'xlsx';

export function asFile(data: Uint8Array | string, name: string): File {
  return new File([data as BlobPart], name);
}

function book(sheets: { name: string; sheet: XLSX.WorkSheet }[]): Uint8Array {
  const workbook = XLSX.utils.book_new();
  for (const { name, sheet } of sheets) XLSX.utils.book_append_sheet(workbook, sheet, name);
  return new Uint8Array(XLSX.write(workbook, { type: 'array', bookType: 'xlsx' }));
}

/**
 * A clean, well-behaved workbook: header on row 1, a formula whose *result*
 * must survive, a real date, and a percentage — the four things a spreadsheet
 * converter most often gets wrong.
 */
export function simpleWorkbook(): Uint8Array {
  const sheet = XLSX.utils.aoa_to_sheet([
    ['Item', 'Qty', 'Unit price', 'Total', 'Ordered', 'Margin'],
    ['Widget', 3, 12.5, null, new Date(Date.UTC(2026, 0, 15)), 0.125],
    ['Gadget', 10, 4, null, new Date(Date.UTC(2026, 1, 2)), 0.4],
  ]);
  // Formulas with a cached result: the converter must emit 37.5, not "=B2*C2".
  sheet['D2'] = { t: 'n', f: 'B2*C2', v: 37.5 };
  sheet['D3'] = { t: 'n', f: 'B3*C3', v: 40 };
  for (const address of ['E2', 'E3']) {
    const cell = sheet[address] as XLSX.CellObject;
    cell.z = 'yyyy-mm-dd';
  }
  for (const address of ['F2', 'F3']) {
    const cell = sheet[address] as XLSX.CellObject;
    cell.z = '0.0%';
  }
  return book([{ name: 'Orders', sheet }]);
}

/**
 * The shape real files arrive in: a title block above the header, spacer rows
 * and columns, a merged category cell spanning three rows, an error cell, and
 * a second sheet in Arabic to prove RTL text is passed through untouched.
 */
export function messyWorkbook(): Uint8Array {
  const main = XLSX.utils.aoa_to_sheet([
    ['Q3 Budget Review', null, null, null, null],
    ['Prepared 4 August 2026', null, null, null, null],
    [null, null, null, null, null],
    ['Category', null, 'Line item', null, 'Amount (JOD)'],
    ['Operations', null, 'Rent', null, 120000],
    [null, null, 'Utilities', null, 18500],
    [null, null, 'Cleaning | security', null, 9000],
    ['Grants', null, 'Sub-grants', null, 450000],
    [null, null, 'Ratio', null, null],
  ]);
  // "Operations" spans A5:A7; only A5 holds the value in the file itself.
  main['!merges'] = [{ s: { r: 4, c: 0 }, e: { r: 6, c: 0 } }];
  // A division by zero, which must show as #DIV/0! rather than vanish.
  main['E9'] = { t: 'e', v: 0x07, f: 'E8/0' };

  const arabic = XLSX.utils.aoa_to_sheet([
    ['الجهة المانحة', 'القطاع', 'القيمة'],
    ['البنك الدولي', 'المياه', 250000],
    ['الاتحاد الأوروبي', 'التعليم', 130000],
  ]);

  const notes = XLSX.utils.aoa_to_sheet([
    ['Outline', 'Note'],
    ['1. Programme', 'Top level'],
    ['   1.1 Water', 'Nested one'],
    ['      1.1.1 Rural', 'Nested two'],
    ['2. Governance', 'Top level'],
  ]);

  const empty = XLSX.utils.aoa_to_sheet([[]]);

  return book([
    { name: 'Budget', sheet: main },
    { name: 'المانحون', sheet: arabic },
    { name: 'Outline', sheet: notes },
    { name: 'Blank', sheet: empty },
  ]);
}

/** 620 data rows, to exercise the truncation threshold and the full-export toggle. */
export function largeWorkbook(rows = 620): Uint8Array {
  const data: (string | number)[][] = [['Ref', 'Portal', 'Value']];
  for (let i = 1; i <= rows; i++) data.push([`REF-${i}`, `Portal ${i % 7}`, i * 100]);
  return book([{ name: 'Notices', sheet: XLSX.utils.aoa_to_sheet(data) }]);
}

/**
 * Semicolon-delimited, BOM-prefixed, with a quoted field containing the
 * delimiter, an embedded newline, a doubled quote and Arabic text — i.e. an
 * export from Excel in a locale where the comma is a decimal separator.
 */
export const messyCsv =
  '﻿' +
  'Ref;Supplier;Notes;Amount\r\n' +
  'A-1;"Al-Nahda; Sons";"Line one\nLine two";"1.250,00"\r\n' +
  'A-2;"He said ""yes""";مذكرة تفاهم;980,50\r\n';

export const simpleCsv = 'name,role\nZiad,Lead\nSara,Analyst\n';
