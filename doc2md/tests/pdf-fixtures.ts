/**
 * PDF fixtures, positioned by hand. Every coordinate matters: the converter
 * infers headings from size, paragraphs from where lines stop, tables from
 * column alignment, and furniture from what repeats — so the fixtures have to
 * state all of that explicitly rather than let a generator choose.
 */
import { PAGE_HEIGHT, PAGE_WIDTH, writePdf, type PageSpec, type TextRun } from './pdf-writer';

const LEFT = 60;
const BODY = 10;

/**
 * A real PDF stores an Arabic run in *visual* order — the layout engine has
 * already laid the glyphs out right to left — and pdf.js reverses it back to
 * logical order on extraction. Writing logical order here would make the
 * fixture test the opposite of what a real file exercises.
 */
export function visualOrder(logical: string): string {
  return [...logical].reverse().join('');
}

export const ARABIC_LINES = ['وزارة التخطيط والتعاون الدولي', 'تعلن عن فرص تمويل جديدة'];

/** Lays runs out downwards from a starting baseline. */
class Cursor {
  private y: number;
  readonly runs: TextRun[] = [];

  constructor(top = PAGE_HEIGHT - 70) {
    this.y = top;
  }

  line(text: string, options: { size?: number; x?: number } = {}): this {
    const size = options.size ?? BODY;
    this.runs.push({ text, x: options.x ?? LEFT, y: this.y, size });
    this.y -= size * 1.6;
    return this;
  }

  row(cells: { text: string; x: number }[], size = BODY): this {
    for (const cell of cells) this.runs.push({ text: cell.text, x: cell.x, y: this.y, size });
    this.y -= size * 1.6;
    return this;
  }

  gap(points: number): this {
    this.y -= points;
    return this;
  }
}

/** Running head and foot, identical on every page bar the page number. */
function furniture(pageNumber: number): TextRun[] {
  return [
    { text: 'Ministry of Planning — Quarterly Review', x: LEFT, y: PAGE_HEIGHT - 30, size: 8 },
    { text: `Page ${pageNumber} of 3`, x: PAGE_WIDTH / 2 - 30, y: 40, size: 8 },
  ];
}

/**
 * Three pages: headings at three sizes, a wrapped paragraph, a bulleted and a
 * numbered list, a three-column table, repeating furniture, an Arabic
 * paragraph, and a page whose only content is that furniture.
 *
 * The first three body lines are deliberately near-identical in length so they
 * all reach the right margin — that is what marks them as wrapped rather than
 * deliberately ended.
 */
export function reportPdf(): Uint8Array {
  const one = new Cursor();
  one.line('Donor Landscape Review', { size: 20 });
  one.gap(6);
  one.line('Executive summary', { size: 14 });
  one.gap(4);
  one.line('Funding across the reviewed portals rose sharply over the period under review,');
  one.line('with the largest single increase recorded in the water sector, where three new');
  one.line('facilities were announced.');
  one.gap(10);
  one.line('A second paragraph starts here and stops short.');
  one.gap(10);
  one.line('Priority sectors', { size: 12 });
  one.gap(4);
  one.line('• Water and sanitation');
  one.line('• Education');
  one.line('• Vocational training', { x: LEFT + 18 });
  one.gap(6);
  one.line('1. Submit the concept note');
  one.line('2. Await clearance');

  const two = new Cursor();
  two.line('Allocations by donor', { size: 14 });
  two.gap(6);
  two.row([
    { text: 'Donor', x: LEFT },
    { text: 'Sector', x: 220 },
    { text: 'Value', x: 380 },
  ]);
  two.row([
    { text: 'World Bank', x: LEFT },
    { text: 'Water', x: 220 },
    { text: '250,000', x: 380 },
  ]);
  two.row([
    { text: 'EBRD', x: LEFT },
    { text: 'Transport', x: 220 },
    { text: '410,000', x: 380 },
  ]);
  two.row([
    { text: 'IsDB', x: LEFT },
    { text: 'Education', x: 220 },
    { text: '130,000', x: 380 },
  ]);
  two.gap(14);
  two.line('Notes in Arabic', { size: 12 });
  two.gap(4);
  for (const arabic of ARABIC_LINES) two.line(visualOrder(arabic));

  const pages: PageSpec[] = [
    { runs: [...one.runs, ...furniture(1)] },
    { runs: [...two.runs, ...furniture(2)] },
    // Page 3 carries only the running head and foot. After those are stripped
    // it contributes nothing — which is not the same as having no text layer.
    { runs: furniture(3) },
  ];
  return writePdf(pages);
}

/** Two pages with no content stream text at all: a scan. */
export function scannedPdf(): Uint8Array {
  return writePdf([{ runs: [] }, { runs: [] }]);
}

/** One page, one heading, one paragraph — the simplest possible document. */
export function simplePdf(): Uint8Array {
  const cursor = new Cursor();
  cursor.line('Field Notes', { size: 18 });
  cursor.gap(6);
  cursor.line('A single paragraph of body text.');
  return writePdf([{ runs: cursor.runs }]);
}

/**
 * Prose that happens to sit in two loose columns. Each line looks like a
 * two-cell row, but the second line has no second column, so the run is not
 * consistently tabular. The converter must fall back to plain text rather than
 * invent a table because something lined up.
 */
export function ambiguousPdf(): Uint8Array {
  const cursor = new Cursor();
  cursor.line('Ambiguous layout', { size: 16 });
  cursor.gap(6);
  cursor.row([
    { text: 'The first note runs here', x: LEFT },
    { text: 'and continues', x: 300 },
  ]);
  cursor.row([{ text: 'A line with no second column at all', x: LEFT }]);
  cursor.row([
    { text: 'Another note', x: LEFT },
    { text: 'with a fragment', x: 300 },
  ]);
  return writePdf([{ runs: cursor.runs }]);
}
