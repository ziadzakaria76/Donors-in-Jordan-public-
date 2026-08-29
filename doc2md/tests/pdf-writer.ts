/**
 * A minimal PDF writer for fixtures.
 *
 * Layout reconstruction is entirely about coordinates and font sizes, so the
 * fixtures have to control both exactly — which rules out a document generator
 * that decides its own line breaking. This writes the objects directly: a page
 * tree, one content stream per page, and two fonts.
 *
 * The second font is a Type0/Identity-H with a ToUnicode CMap and no embedded
 * font file. Text extraction only needs the CMap, so this is enough to put
 * genuine Arabic codepoints into a PDF without committing a TTF to the repo.
 */

export interface TextRun {
  text: string;
  x: number;
  /** Measured from the bottom of the page, as PDF coordinates are. */
  y: number;
  size: number;
}

/**
 * Anything outside printable ASCII goes through the Type0 font. Writing a
 * bullet or an em dash as a raw byte in a WinAnsi literal string silently
 * produces a different character, which then shows up as a converter bug that
 * is really a fixture bug.
 */
function needsUnicodeFont(text: string): boolean {
  return /[^\x20-\x7E]/.test(text);
}

export interface PageSpec {
  runs: TextRun[];
}

export const PAGE_WIDTH = 595;
export const PAGE_HEIGHT = 842;

/** Widths are only used to place runs; 0.5em per glyph is close enough. */
export const CHAR_WIDTH = 0.5;

export function textWidth(text: string, size: number): number {
  return text.length * size * CHAR_WIDTH;
}

function escapeLiteral(text: string): string {
  return text.replace(/([\\()])/g, '\\$1');
}

export function writePdf(pages: PageSpec[]): Uint8Array {
  // Every character used in a unicode run gets a CID, in first-seen order.
  const cids = new Map<string, number>();
  for (const page of pages) {
    for (const run of page.runs) {
      if (!needsUnicodeFont(run.text)) continue;
      for (const character of [...run.text]) {
        if (!cids.has(character)) cids.set(character, cids.size + 1);
      }
    }
  }

  const objects: string[] = [];
  /** Reserves an object number; bodies are filled in below. */
  const reserve = (): number => {
    objects.push('');
    return objects.length;
  };

  const catalog = reserve();
  const pageTree = reserve();
  const helvetica = reserve();
  const type0 = reserve();
  const cidFont = reserve();
  const descriptor = reserve();
  const toUnicode = reserve();

  const pageIds: number[] = [];
  const contentIds: number[] = [];
  for (const _page of pages) {
    void _page;
    pageIds.push(reserve());
    contentIds.push(reserve());
  }

  objects[catalog - 1] = `<< /Type /Catalog /Pages ${pageTree} 0 R >>`;
  objects[pageTree - 1] =
    `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pages.length} >>`;
  objects[helvetica - 1] =
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>';
  objects[type0 - 1] =
    `<< /Type /Font /Subtype /Type0 /BaseFont /Doc2MDTest /Encoding /Identity-H ` +
    `/DescendantFonts [${cidFont} 0 R] /ToUnicode ${toUnicode} 0 R >>`;
  objects[cidFont - 1] =
    `<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Doc2MDTest ` +
    `/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> ` +
    `/FontDescriptor ${descriptor} 0 R /DW 500 >>`;
  objects[descriptor - 1] =
    `<< /Type /FontDescriptor /FontName /Doc2MDTest /Flags 4 /FontBBox [0 -200 1000 800] ` +
    `/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>`;
  objects[toUnicode - 1] = streamObject(cmap(cids));

  pages.forEach((page, index) => {
    objects[pageIds[index]! - 1] =
      `<< /Type /Page /Parent ${pageTree} 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] ` +
      `/Resources << /Font << /F1 ${helvetica} 0 R /F2 ${type0} 0 R >> >> ` +
      `/Contents ${contentIds[index]} 0 R >>`;
    objects[contentIds[index]! - 1] = streamObject(contentStream(page, cids));
  });

  return assemble(objects, catalog);
}

function contentStream(page: PageSpec, cids: Map<string, number>): string {
  const parts: string[] = [];
  for (const run of page.runs) {
    if (run.text === '') continue;
    const unicode = needsUnicodeFont(run.text);
    const font = unicode ? '/F2' : '/F1';
    const show = unicode
      ? `<${[...run.text]
          .map((character) => (cids.get(character) ?? 0).toString(16).padStart(4, '0'))
          .join('')}>`
      : `(${escapeLiteral(run.text)})`;
    parts.push(
      `BT ${font} ${run.size} Tf 1 0 0 1 ${round(run.x)} ${round(run.y)} Tm ${show} Tj ET`,
    );
  }
  return parts.join('\n');
}

function cmap(cids: Map<string, number>): string {
  const entries = [...cids.entries()].map(
    ([character, cid]) =>
      `<${cid.toString(16).padStart(4, '0')}> <${character
        .codePointAt(0)!
        .toString(16)
        .padStart(4, '0')
        .toUpperCase()}>`,
  );
  // beginbfchar takes at most 100 entries per block.
  const blocks: string[] = [];
  for (let i = 0; i < entries.length; i += 100) {
    const chunk = entries.slice(i, i + 100);
    blocks.push(`${chunk.length} beginbfchar\n${chunk.join('\n')}\nendbfchar`);
  }
  return [
    '/CIDInit /ProcSet findresource begin',
    '12 dict begin',
    'begincmap',
    '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
    '/CMapName /Adobe-Identity-UCS def',
    '/CMapType 2 def',
    '1 begincodespacerange',
    '<0000> <FFFF>',
    'endcodespacerange',
    ...blocks,
    'endcmap',
    'CMapName currentdict /CMap defineresource pop',
    'end',
    'end',
  ].join('\n');
}

function streamObject(body: string): string {
  return `<< /Length ${byteLength(body)} >>\nstream\n${body}\nendstream`;
}

function byteLength(text: string): number {
  return new TextEncoder().encode(text).length;
}

function round(value: number): string {
  return (Math.round(value * 100) / 100).toString();
}

/** Serialises the objects with a real cross-reference table. */
function assemble(objects: string[], rootId: number): Uint8Array {
  let output = '%PDF-1.7\n';
  const offsets: number[] = [];
  objects.forEach((body, index) => {
    offsets.push(byteLength(output));
    output += `${index + 1} 0 obj\n${body}\nendobj\n`;
  });

  const xrefOffset = byteLength(output);
  output += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) {
    output += `${offset.toString().padStart(10, '0')} 00000 n \n`;
  }
  output += `trailer\n<< /Size ${objects.length + 1} /Root ${rootId} 0 R >>\n`;
  output += `startxref\n${xrefOffset}\n%%EOF\n`;

  // latin1 keeps every byte value intact; the streams are ASCII apart from the
  // hex-encoded CIDs, which are ASCII too.
  return Uint8Array.from(output, (character) => character.charCodeAt(0) & 0xff);
}
