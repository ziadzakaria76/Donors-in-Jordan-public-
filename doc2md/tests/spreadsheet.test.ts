import { describe, expect, it } from 'vitest';
import { convert } from '../src/converters/spreadsheet';
import type { ConversionResult } from '../src/core/types';
import {
  asFile,
  largeWorkbook,
  messyCsv,
  messyWorkbook,
  simpleCsv,
  simpleWorkbook,
} from './fixtures';

const run = (
  data: Uint8Array | string,
  name: string,
  fullExport = false,
): Promise<ConversionResult> => convert(asFile(data, name), { fullExport });

describe('spreadsheet converter — XLSX', () => {
  it('converts a clean workbook', async () => {
    const { markdown, meta } = await run(simpleWorkbook(), 'orders.xlsx');
    expect(meta.sheets).toEqual(['Orders']);
    expect(markdown).toMatchSnapshot();
  });

  it('emits formula results, not formulas', async () => {
    const { markdown } = await run(simpleWorkbook(), 'orders.xlsx');
    expect(markdown).toContain('37.5');
    expect(markdown).not.toContain('B2*C2');
    expect(markdown).not.toContain('=');
  });

  it('keeps dates and percentages in their displayed format', async () => {
    const { markdown } = await run(simpleWorkbook(), 'orders.xlsx');
    expect(markdown).toContain('2026-01-15');
    expect(markdown).toContain('12.5%');
    // The date serial must not leak through.
    expect(markdown).not.toContain('46037');
  });

  it('right-aligns numeric columns and left-aligns text ones', async () => {
    const { markdown } = await run(simpleWorkbook(), 'orders.xlsx');
    expect(markdown).toContain('| --- | ---: | ---: | ---: | --- | ---: |');
  });

  it('handles a messy workbook: titles, merges, spacers, RTL, errors', async () => {
    const { markdown } = await run(messyWorkbook(), 'budget.xlsx');
    expect(markdown).toMatchSnapshot();
  });

  it('finds the real header row under a title block', async () => {
    const { markdown } = await run(messyWorkbook(), 'budget.xlsx');
    expect(markdown).toContain('| Category | Line item | Amount (JOD) |');
    // The title survives, above the table, rather than becoming the header.
    expect(markdown).toContain('Q3 Budget Review');
    expect(markdown.indexOf('Q3 Budget Review')).toBeLessThan(
      markdown.indexOf('| Category |'),
    );
  });

  it('repeats a merged cell down its range', async () => {
    const { markdown } = await run(messyWorkbook(), 'budget.xlsx');
    expect(markdown).toContain('| Operations | Utilities |');
    expect(markdown).toContain('| Operations | Cleaning \\| security |');
  });

  it('escapes pipes so a cell cannot break the table', async () => {
    const { markdown } = await run(messyWorkbook(), 'budget.xlsx');
    const rows = markdown.split('\n').filter((line) => line.startsWith('| Operations'));
    for (const row of rows) {
      expect(row.split(/(?<!\\)\|/).length).toBe(5); // 3 cells → 4 delimiters + 1
    }
  });

  it('shows a formula error as Excel shows it', async () => {
    const { markdown } = await run(messyWorkbook(), 'budget.xlsx');
    expect(markdown).toContain('#DIV/0!');
  });

  it('passes Arabic through unreversed, in a sheet named in Arabic', async () => {
    const { markdown, meta } = await run(messyWorkbook(), 'budget.xlsx');
    expect(meta.sheets).toContain('المانحون');
    expect(markdown).toContain('## Sheet: المانحون');
    expect(markdown).toContain('| البنك الدولي | المياه |');
  });

  it('marks an empty sheet instead of dropping it', async () => {
    const { markdown } = await run(messyWorkbook(), 'budget.xlsx');
    expect(markdown).toContain('## Sheet: Blank\n\n<!-- empty sheet -->');
  });

  it('preserves the indentation that carries outline nesting', async () => {
    const { markdown } = await run(messyWorkbook(), 'budget.xlsx');
    // Trimming these would silently flatten a three-level outline into a list.
    expect(markdown).toContain('| 1. Programme |');
    expect(markdown).toContain('|    1.1 Water |');
    expect(markdown).toContain('|       1.1.1 Rural |');
  });
});

describe('spreadsheet converter — truncation', () => {
  it('cuts a long sheet down and says so', async () => {
    const { markdown, meta } = await run(largeWorkbook(), 'notices.xlsx');
    expect(markdown).toContain('<!-- truncated: 620 rows total, showing the first 100 -->');
    expect(markdown).toContain('REF-100');
    expect(markdown).not.toContain('REF-101');
    expect(meta.warnings).toEqual([
      'Sheet "Notices": showing 100 of 620 rows. Turn on "Full export" to include them all.',
    ]);
  });

  it('emits everything when full export is on', async () => {
    const { markdown, meta } = await run(largeWorkbook(), 'notices.xlsx', true);
    expect(markdown).toContain('REF-620');
    expect(markdown).not.toContain('truncated');
    expect(meta.warnings).toEqual([]);
  });

  it('leaves a sheet at the threshold alone', async () => {
    const { markdown } = await run(largeWorkbook(500), 'notices.xlsx');
    expect(markdown).toContain('REF-500');
    expect(markdown).not.toContain('truncated');
  });
});

describe('spreadsheet converter — CSV', () => {
  it('converts a simple comma file', async () => {
    const { markdown } = await run(simpleCsv, 'people.csv');
    expect(markdown).toBe(
      ['# people', '', '| name | role |', '| --- | --- |', '| Ziad | Lead |', '| Sara | Analyst |'].join('\n'),
    );
  });

  it('handles BOM, semicolons, quotes, newlines and Arabic', async () => {
    const { markdown } = await run(messyCsv, 'suppliers.csv');
    expect(markdown).toMatchSnapshot();
  });

  it('does not coerce values the way a spreadsheet engine would', async () => {
    const { markdown } = await run('code,qty\n007,1.0\n', 'codes.csv');
    expect(markdown).toContain('| 007 | 1.0 |');
  });

  it('reports no rows rather than an empty table', async () => {
    const { markdown } = await run('\n\n', 'blank.csv');
    expect(markdown).toContain('<!-- no rows -->');
  });
});
