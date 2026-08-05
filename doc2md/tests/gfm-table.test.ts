import { describe, expect, it } from 'vitest';
import {
  detectHeaderRow,
  escapeCell,
  inferAlignments,
  looksNumeric,
  normalizeGrid,
  renderTable,
} from '../src/core/gfm-table';

describe('normalizeGrid', () => {
  it('squares off ragged rows', () => {
    expect(normalizeGrid([['a'], ['b', 'c', 'd']])).toEqual([
      ['a', '', ''],
      ['b', 'c', 'd'],
    ]);
  });

  it('drops fully empty rows and columns, including interior ones', () => {
    expect(
      normalizeGrid([
        ['a', '', 'b'],
        ['', '', ''],
        ['c', '', 'd'],
      ]),
    ).toEqual([
      ['a', 'b'],
      ['c', 'd'],
    ]);
  });

  it('blanks a whitespace-only cell without flattening real indentation', () => {
    expect(normalizeGrid([['  ', 'x'], ['   indented', 'y']])).toEqual([
      ['', 'x'],
      ['   indented', 'y'],
    ]);
    expect(normalizeGrid([['   ', '   ']])).toEqual([]);
  });

  it('returns nothing for an empty grid', () => {
    expect(normalizeGrid([])).toEqual([]);
    expect(normalizeGrid([[], []])).toEqual([]);
  });
});

describe('detectHeaderRow', () => {
  it('takes row 0 when the sheet is already clean', () => {
    expect(
      detectHeaderRow([
        ['Name', 'Qty', 'Price'],
        ['Widget', '3', '12.50'],
        ['Gadget', '9', '4.00'],
      ]),
    ).toBe(0);
  });

  it('skips a narrow title row', () => {
    expect(
      detectHeaderRow([
        ['Q3 Budget Review', '', ''],
        ['Item', 'Owner', 'Amount'],
        ['Rent', 'Ops', '120000'],
        ['Utilities', 'Ops', '18500'],
      ]),
    ).toBe(1);
  });

  it('skips a full-width row of numbers that only looks like a header', () => {
    expect(
      detectHeaderRow([
        ['2024', '2025', '2026'],
        ['Region', 'Spend', 'Share'],
        ['North', '100', '40%'],
        ['South', '150', '60%'],
      ]),
    ).toBe(1);
  });

  it('prefers distinct labels over a repeated one', () => {
    expect(
      detectHeaderRow([
        ['JOD', 'JOD', 'JOD'],
        ['Donor', 'Sector', 'Value'],
        ['World Bank', 'Water', '250000'],
      ]),
    ).toBe(1);
  });

  it('does not run off the end of a one-row or two-row grid', () => {
    expect(detectHeaderRow([['only', 'row']])).toBe(0);
    expect(detectHeaderRow([['a', 'b'], ['1', '2']])).toBe(0);
  });
});

describe('looksNumeric', () => {
  it('accepts the shapes a spreadsheet actually produces', () => {
    for (const value of ['12', '-3.5', '1,250', '1 250', '$40', '12.5%', '(900)', '1.2e6', '٩٨٠']) {
      expect(looksNumeric(value), value).toBe(true);
    }
  });

  it('rejects text, blanks and mixed content', () => {
    for (const value of ['', 'Q3', '12 items', 'REF-4', '2026-01-15']) {
      expect(looksNumeric(value), value).toBe(false);
    }
  });
});

describe('escapeCell', () => {
  it('escapes pipes and folds newlines so the table survives', () => {
    expect(escapeCell('a | b')).toBe('a \\| b');
    expect(escapeCell('one\ntwo')).toBe('one<br>two');
    expect(escapeCell('one\r\ntwo')).toBe('one<br>two');
  });

  it('strips control characters', () => {
    expect(escapeCell('a\u0007b\u001Fc')).toBe('abc');
  });

  it('keeps leading indentation but not trailing space', () => {
    expect(escapeCell('   nested   ')).toBe('   nested');
    expect(escapeCell('    ')).toBe('');
  });
});

describe('inferAlignments', () => {
  it('right-aligns a mostly-numeric column', () => {
    expect(
      inferAlignments(
        [
          ['Rent', '120000'],
          ['Utilities', '18500'],
          ['Ratio', 'n/a'],
        ],
        2,
      ),
    ).toEqual(['left', 'right']);
  });

  it('leaves an empty column alone', () => {
    expect(inferAlignments([['', '']], 2)).toEqual(['left', 'left']);
  });
});

describe('renderTable', () => {
  it('pads a short row to the header width', () => {
    expect(renderTable(['A', 'B', 'C'], [['1']], ['left', 'left', 'right'])).toBe(
      ['| A | B | C |', '| --- | --- | ---: |', '| 1 |  |  |'].join('\n'),
    );
  });
});
