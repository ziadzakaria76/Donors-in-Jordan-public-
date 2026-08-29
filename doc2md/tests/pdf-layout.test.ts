import { describe, expect, it } from 'vitest';
import {
  blocksToMarkdown,
  buildLines,
  findFurniture,
  findTables,
  furnitureKey,
  headingLevel,
  headingScale,
  pageBlocks,
  type PageLayout,
  type Piece,
} from '../src/converters/pdf-layout';

const piece = (
  text: string,
  x: number,
  y: number,
  options: { size?: number; width?: number; rtl?: boolean } = {},
): Piece => ({
  text,
  x,
  y,
  size: options.size ?? 10,
  // Half an em per character is close enough for layout decisions.
  width: options.width ?? text.length * (options.size ?? 10) * 0.5,
  rtl: options.rtl ?? false,
});

const page = (lines: Piece[], overrides: Partial<PageLayout> = {}): PageLayout => ({
  number: 1,
  width: 595,
  height: 842,
  lines: buildLines(lines),
  ...overrides,
});

describe('buildLines', () => {
  it('groups runs sharing a baseline and orders them left to right', () => {
    const lines = buildLines([piece('world', 100, 700), piece('Hello', 60, 700)]);
    expect(lines).toHaveLength(1);
    expect(lines[0]!.text).toBe('Hello world');
  });

  it('separates baselines that are far enough apart', () => {
    expect(buildLines([piece('one', 60, 700), piece('two', 60, 684)])).toHaveLength(2);
  });

  it('keeps a subscript on the same line as its baseline', () => {
    const lines = buildLines([piece('H', 60, 700), piece('2', 66, 697, { size: 6 })]);
    expect(lines).toHaveLength(1);
  });

  it('reads a right-to-left line in logical order without reversing any run', () => {
    // Laid out visually: the last logical word sits leftmost.
    const lines = buildLines([
      piece('الدولي', 60, 700, { rtl: true }),
      piece('وزارة', 160, 700, { rtl: true }),
    ]);
    expect(lines[0]!.text).toBe('وزارة الدولي');
    expect(lines[0]!.rtl).toBe(true);
  });

  it('treats a wide whitespace run as a column break, not a word space', () => {
    // pdf.js reports a column gap as one space whose width spans the gap.
    const lines = buildLines([
      piece('Donor', 60, 700),
      piece(' ', 87, 700, { width: 133 }),
      piece('Sector', 220, 700),
    ]);
    expect(lines[0]!.segments.map((segment) => segment.text)).toEqual(['Donor', 'Sector']);
  });

  it('treats a narrow whitespace run as an ordinary space', () => {
    const lines = buildLines([
      piece('Donor', 60, 700),
      piece(' ', 85, 700, { width: 3 }),
      piece('list', 88, 700),
    ]);
    expect(lines[0]!.segments).toHaveLength(1);
    expect(lines[0]!.text).toBe('Donor list');
  });

  it('returns nothing for a page with no text', () => {
    expect(buildLines([])).toEqual([]);
    expect(buildLines([piece('', 0, 0)])).toEqual([]);
  });
});

describe('headingScale', () => {
  const layout = page([
    piece('Big Title', 60, 800, { size: 20 }),
    piece('Section', 60, 760, { size: 14 }),
    piece('Subsection', 60, 730, { size: 12 }),
    piece('Body text that carries most of the characters on this page', 60, 700),
    piece('More body text, so ten point is clearly the body size', 60, 684),
  ]);

  it('picks the size carrying the most characters as body text', () => {
    expect(headingScale([layout]).body).toBe(10);
  });

  it('ranks larger sizes into consecutive heading levels', () => {
    const scale = headingScale([layout]);
    expect(scale.levels).toEqual([20, 14, 12]);
    expect(headingLevel(layout.lines[0]!, scale)).toBe(1);
    expect(headingLevel(layout.lines[1]!, scale)).toBe(2);
    expect(headingLevel(layout.lines[2]!, scale)).toBe(3);
    expect(headingLevel(layout.lines[3]!, scale)).toBeNull();
  });

  it('refuses to call a long line a heading however big it is', () => {
    const long = page([
      piece('x'.repeat(200), 60, 800, { size: 20 }),
      piece('body', 60, 700),
      piece('body again', 60, 684),
    ]);
    expect(headingLevel(long.lines[0]!, headingScale([long]))).toBeNull();
  });

  it('copes with a document that has no text at all', () => {
    expect(headingScale([page([])])).toEqual({ body: 0, levels: [] });
  });
});

describe('findFurniture', () => {
  const withFurniture = (n: number): PageLayout =>
    page(
      [
        piece('Ministry of Planning — Quarterly Review', 60, 812, { size: 8 }),
        piece(`Body of page ${n}`, 60, 700),
        piece(`Page ${n} of 4`, 260, 40, { size: 8 }),
      ],
      { number: n },
    );

  it('normalises digits so a numbered footer matches across pages', () => {
    expect(furnitureKey('Page 3 of 10')).toBe(furnitureKey('Page 7 of 10'));
    expect(furnitureKey('Page 3 of 10')).toBe('page # of #');
  });

  it('finds lines repeating in the margins of most pages', () => {
    const pages = [1, 2, 3, 4].map(withFurniture);
    const furniture = findFurniture(pages);
    expect(furniture.has(furnitureKey('Ministry of Planning — Quarterly Review'))).toBe(true);
    expect(furniture.has(furnitureKey('Body of page 1'))).toBe(false);
  });

  it('ignores repetition when there are too few pages to judge', () => {
    expect(findFurniture([withFurniture(1), withFurniture(2)]).size).toBe(0);
  });

  it('strips the furniture from the rendered page', () => {
    const pages = [1, 2, 3, 4].map(withFurniture);
    const furniture = findFurniture(pages);
    const markdown = blocksToMarkdown(
      pageBlocks(pages[0]!, headingScale(pages, furniture), furniture),
    );
    expect(markdown).toBe('Body of page 1');
  });

  it('does not let small repeated furniture masquerade as the body size', () => {
    // The 8pt running head and foot carry more characters than the 10pt body,
    // so counting them would make the real body text look like a heading.
    const pages = [1, 2, 3, 4].map(withFurniture);
    expect(headingScale(pages, findFurniture(pages)).body).toBe(10);
    expect(headingScale(pages).body).toBe(8);
  });
});

describe('findTables', () => {
  const row = (cells: [string, number][], y: number): Piece[] =>
    cells.flatMap(([text, x], index) => {
      const previous = cells[index - 1];
      const pieces: Piece[] = [];
      if (previous) {
        const previousRight = previous[1] + previous[0].length * 5;
        pieces.push(piece(' ', previousRight, y, { width: x - previousRight }));
      }
      pieces.push(piece(text, x, y));
      return pieces;
    });

  it('finds a table from consistently aligned columns', () => {
    const lines = buildLines([
      ...row([['Donor', 60], ['Sector', 220], ['Value', 380]], 700),
      ...row([['World Bank', 60], ['Water', 220], ['250,000', 380]], 684),
      ...row([['EBRD', 60], ['Transport', 220], ['410,000', 380]], 668),
    ]);
    const tables = findTables(lines, 595);
    expect(tables).toHaveLength(1);
    expect(tables[0]!.grid).toEqual([
      ['Donor', 'Sector', 'Value'],
      ['World Bank', 'Water', '250,000'],
      ['EBRD', 'Transport', '410,000'],
    ]);
  });

  it('refuses a run of only two rows', () => {
    const lines = buildLines([
      ...row([['A', 60], ['B', 220]], 700),
      ...row([['C', 60], ['D', 220]], 684),
    ]);
    expect(findTables(lines, 595)).toEqual([]);
  });

  it('refuses columns that do not line up between rows', () => {
    const lines = buildLines([
      ...row([['A', 60], ['B', 220]], 700),
      ...row([['C', 60], ['D', 300]], 684),
      ...row([['E', 60], ['F', 170]], 668),
    ]);
    expect(findTables(lines, 595)).toEqual([]);
  });
});

describe('pageBlocks', () => {
  const render = (pieces: Piece[]): string => {
    const layout = page(pieces);
    return blocksToMarkdown(pageBlocks(layout, headingScale([layout]), new Set()));
  };

  it('joins wrapped lines and breaks where a line stops short', () => {
    const markdown = render([
      piece('The first line of this paragraph reaches the right margin exactly', 60, 700),
      piece('and the second line of it also reaches the right margin here', 60, 684),
      piece('but this one stops.', 60, 668),
      piece('A new paragraph, well separated from the last.', 60, 620),
    ]);
    expect(markdown).toContain(
      'The first line of this paragraph reaches the right margin exactly and the second line of it also reaches the right margin here but this one stops.',
    );
    expect(markdown).toContain('\n\nA new paragraph, well separated from the last.');
  });

  it('starts a new paragraph when the vertical gap widens, whatever the margin', () => {
    const markdown = render([
      piece('A line that runs right out to the margin of the page here', 60, 700),
      piece('Another line far below it entirely', 60, 560),
    ]);
    expect(markdown.split('\n\n')).toHaveLength(2);
  });

  it('detects bullets and nests them by indentation', () => {
    expect(
      render([
        piece('• Water', 60, 700),
        piece('• Education', 60, 684),
        piece('• Vocational training', 78, 668),
      ]),
    ).toBe('- Water\n- Education\n  - Vocational training');
  });

  it('renumbers an ordered list and keeps it apart from a bulleted one', () => {
    const markdown = render([
      piece('• Water', 60, 700),
      piece('1. First step', 60, 684),
      piece('2. Second step', 60, 668),
    ]);
    expect(markdown).toBe('- Water\n\n1. First step\n2. Second step');
  });

  it('does not mistake a year for a list marker', () => {
    expect(render([piece('1990. A year, not a numbered item.', 60, 700)])).toBe(
      '1990. A year, not a numbered item.',
    );
  });
});
