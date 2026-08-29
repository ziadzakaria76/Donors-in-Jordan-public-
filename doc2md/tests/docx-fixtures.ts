/**
 * Real .docx files built in code, so the snapshots assert against documents a
 * reviewer can read the definition of. Uses the `docx` package (dev-only) —
 * hand-rolling OOXML numbering and footnote parts would be a lot of XML for
 * no extra confidence.
 */
import {
  AlignmentType,
  Document,
  ExternalHyperlink,
  Footer,
  FootnoteReferenceRun,
  Header,
  HeadingLevel,
  ImageRun,
  LevelFormat,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from 'docx';

/** A 1x1 transparent PNG, so an image exists without any real bytes mattering. */
const PNG_1PX = Uint8Array.from(
  atob(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  ),
  (character) => character.charCodeAt(0),
);

const NUMBERING = {
  config: [
    {
      reference: 'outline',
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT },
        { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT },
        { level: 2, format: LevelFormat.BULLET, text: '▪', alignment: AlignmentType.LEFT },
      ],
    },
    {
      reference: 'steps',
      levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT },
        { level: 1, format: LevelFormat.LOWER_LETTER, text: '%2.', alignment: AlignmentType.LEFT },
      ],
    },
  ],
};

async function pack(document: Document): Promise<Uint8Array> {
  return new Uint8Array(await Packer.toBuffer(document));
}

/**
 * Exercises the whole feature list in one document: headings 1–3, bold and
 * italic, a hyperlink, nested bulleted and numbered lists, a block quote, a
 * table with both a column span and a row span, a footnote, an image, and
 * Arabic in a right-to-left paragraph.
 */
export function richDocument(): Promise<Uint8Array> {
  return pack(
    new Document({
      numbering: NUMBERING,
      // Word ships this style; the `docx` package does not, and an undefined
      // style ID is invisible to mammoth's style-name mapping.
      styles: {
        paragraphStyles: [
          { id: 'IntenseQuote', name: 'Intense Quote', basedOn: 'Normal', quickFormat: true },
        ],
      },
      footnotes: {
        1: { children: [new Paragraph('Figures are provisional pending audit.')] },
        2: { children: [new Paragraph('Converted at the 2026 average rate.')] },
      },
      sections: [
        {
          // Repeated on every page, so it must not end up in the body text.
          headers: { default: new Header({ children: [new Paragraph('Confidential draft')] }) },
          footers: { default: new Footer({ children: [new Paragraph('Page 1')] }) },
          children: [
            new Paragraph({ text: 'Donor Landscape Review', heading: HeadingLevel.HEADING_1 }),
            new Paragraph({ text: 'Executive summary', heading: HeadingLevel.HEADING_2 }),
            new Paragraph({
              children: [
                new TextRun('Funding rose by '),
                new TextRun({ text: '18%', bold: true }),
                new TextRun(' against a '),
                new TextRun({ text: 'falling', italics: true }),
                new TextRun(' baseline'),
                new FootnoteReferenceRun(1),
                new TextRun('. See the '),
                new ExternalHyperlink({
                  children: [new TextRun('portal listing')],
                  link: 'https://example.org/notices',
                }),
                new TextRun(' for detail.'),
              ],
            }),
            new Paragraph({ text: 'Priority sectors', heading: HeadingLevel.HEADING_3 }),
            new Paragraph({ text: 'Water', numbering: { reference: 'outline', level: 0 } }),
            new Paragraph({ text: 'Rural supply', numbering: { reference: 'outline', level: 1 } }),
            new Paragraph({ text: 'Metering', numbering: { reference: 'outline', level: 2 } }),
            new Paragraph({ text: 'Education', numbering: { reference: 'outline', level: 0 } }),
            new Paragraph({ text: 'Submit the concept note', numbering: { reference: 'steps', level: 0 } }),
            new Paragraph({ text: 'Attach the budget', numbering: { reference: 'steps', level: 1 } }),
            new Paragraph({ text: 'Await clearance', numbering: { reference: 'steps', level: 0 } }),
            new Paragraph({
              text: 'The window closes at the end of the quarter.',
              style: 'IntenseQuote',
            }),
            new Paragraph({
              children: [
                new TextRun('وزارة التخطيط والتعاون الدولي تعلن عن فرص جديدة'),
                new FootnoteReferenceRun(2),
              ],
              bidirectional: true,
            }),
            new Table({
              width: { size: 100, type: WidthType.PERCENTAGE },
              rows: [
                new TableRow({
                  children: [
                    new TableCell({ children: [new Paragraph('Donor')] }),
                    new TableCell({ children: [new Paragraph('Sector')] }),
                    new TableCell({ children: [new Paragraph('Value')] }),
                  ],
                }),
                new TableRow({
                  children: [
                    // Spans this row and the next: the value must be repeated.
                    new TableCell({ rowSpan: 2, children: [new Paragraph('World Bank')] }),
                    new TableCell({ children: [new Paragraph('Water')] }),
                    new TableCell({ children: [new Paragraph('250,000')] }),
                  ],
                }),
                new TableRow({
                  children: [
                    new TableCell({ children: [new Paragraph('Education')] }),
                    new TableCell({ children: [new Paragraph('130,000')] }),
                  ],
                }),
                new TableRow({
                  children: [
                    // Spans two columns.
                    new TableCell({ columnSpan: 2, children: [new Paragraph('Total | all sectors')] }),
                    new TableCell({ children: [new Paragraph('380,000')] }),
                  ],
                }),
              ],
            }),
            new Paragraph({
              children: [
                new ImageRun({
                  type: 'png',
                  data: PNG_1PX,
                  transformation: { width: 40, height: 40 },
                  altText: { name: 'chart', description: 'Funding by sector', title: 'chart' },
                }),
              ],
            }),
          ],
        },
      ],
    }),
  );
}

/** The minimum case: one heading, one paragraph, nothing else. */
export function plainDocument(): Promise<Uint8Array> {
  return pack(
    new Document({
      sections: [
        {
          children: [
            new Paragraph({ text: 'Notes', heading: HeadingLevel.HEADING_1 }),
            new Paragraph('A single paragraph of body text.'),
          ],
        },
      ],
    }),
  );
}

/** A document whose only content is a table, to check nothing is prepended. */
export function tableOnlyDocument(): Promise<Uint8Array> {
  return pack(
    new Document({
      sections: [
        {
          children: [
            new Table({
              rows: [
                new TableRow({
                  children: [
                    new TableCell({ children: [new Paragraph('Ref')] }),
                    new TableCell({ children: [new Paragraph('Amount')] }),
                  ],
                }),
                new TableRow({
                  children: [
                    new TableCell({ children: [new Paragraph('A-1')] }),
                    new TableCell({ children: [new Paragraph('1200')] }),
                  ],
                }),
              ],
            }),
          ],
        },
      ],
    }),
  );
}
