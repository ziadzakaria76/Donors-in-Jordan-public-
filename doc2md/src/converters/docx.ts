import type TurndownService from 'turndown';
import { inferAlignments, renderTable, type Grid } from '../core/gfm-table';
import { ConversionError, type Converter } from '../core/types';

interface ImageRef {
  name: string;
  contentType: string;
  alt: string;
}

const IMAGE_EXTENSIONS: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/gif': 'gif',
  'image/bmp': 'bmp',
  'image/tiff': 'tiff',
  'image/svg+xml': 'svg',
  'image/webp': 'webp',
  'image/x-emf': 'emf',
  'image/x-wmf': 'wmf',
};

/**
 * Mapping is by Word *style name*, never by font size — a 14pt bold paragraph
 * is not a heading, and a document that styles Heading 3 smaller than body text
 * still has a Heading 3 in it. mammoth's default map already covers Heading 1–6
 * and lists; these are the everyday styles it leaves alone.
 */
const STYLE_MAP = [
  "p[style-name='Title'] => h1:fresh",
  "p[style-name='Subtitle'] => p:fresh",
  "p[style-name='Quote'] => blockquote:fresh",
  "p[style-name='Intense Quote'] => blockquote:fresh",
  "p[style-name='Block Text'] => blockquote:fresh",
  "p[style-name='Block Quote'] => blockquote:fresh",
  "r[style-name='Code Char'] => code",
  "r[style-name='Inline Code'] => code",
  "r[style-name='HTML Code'] => code",
];

/** How many distinct mammoth complaints to surface before summarising. */
const MAX_REPORTED_WARNINGS = 4;

export const convert: Converter = async (file, options) => {
  options.onProgress?.(0.05, 'Reading document');

  const [mammothModule, turndownModule, gfmModule] = await Promise.all([
    import('mammoth'),
    import('turndown'),
    import('turndown-plugin-gfm'),
  ]);
  const mammoth = mammothModule.default;
  const Turndown = turndownModule.default;

  const images: ImageRef[] = [];
  const bytes = await file.arrayBuffer();
  let result;
  try {
    result = await mammoth.convertToHtml(
      // mammoth's browser entry reads `arrayBuffer` and its Node entry reads
      // `buffer`; both hand the same value to the same unzip call. Supplying
      // both costs nothing and lets the test suite exercise this exact code
      // path under Node instead of a mocked variant of it.
      { arrayBuffer: bytes, buffer: bytes } as unknown as { arrayBuffer: ArrayBuffer },
      {
        styleMap: STYLE_MAP,
        convertImage: mammoth.images.imgElement((image) => {
          const name = `image-${images.length + 1}.${IMAGE_EXTENSIONS[image.contentType] ?? 'bin'}`;
          images.push({
            name,
            contentType: image.contentType,
            // Present on the runtime object; absent from the published types.
            alt: (image as { altText?: string }).altText ?? '',
          });
          // The bytes are never read. `image.read()` is what produces a base64
          // data URI, and a 2 MB screenshot inlined into Markdown is exactly
          // the kind of thing this tool exists to avoid.
          return Promise.resolve({ src: name });
        }),
      },
    );
  } catch (error) {
    throw new ConversionError(
      'Could not read this document — it may be password-protected, corrupt, or not a real .docx.',
      { cause: error },
    );
  }

  options.onProgress?.(0.6, 'Converting');
  const service = createTurndown(Turndown, gfmModule.strikethrough, gfmModule.taskListItems);
  const body = service.turndown(result.value).trim();

  const sections = [body];
  if (images.length > 0) sections.push(imageFooter(images));

  options.onProgress?.(1, 'Done');
  return {
    markdown: sections.join('\n\n'),
    meta: {
      images: images.map((image) => image.name),
      warnings: summariseMessages(result.messages),
    },
  };
};

// ------------------------------------------------------------------ turndown

type TurndownConstructor = typeof TurndownService;
type Plugin = (service: TurndownService) => void;

function createTurndown(
  Turndown: TurndownConstructor,
  ...plugins: Plugin[]
): TurndownService {
  const service = new Turndown({
    headingStyle: 'atx',
    hr: '---',
    bulletListMarker: '-',
    codeBlockStyle: 'fenced',
    emDelimiter: '*',
    strongDelimiter: '**',
    linkStyle: 'inlined',
  });
  for (const plugin of plugins) service.use(plugin);

  // Rules added later are matched first, so these override the built-ins.
  addListItemRule(service);
  addImageRule(service);
  addFootnoteRules(service);
  addTableRule(service);
  return service;
}

/**
 * turndown pads list markers out to four columns (`-   item`) and indents
 * nested lists by four spaces. Both are valid and both are wasted tokens on
 * every line of every list. This emits the minimum CommonMark accepts: the
 * marker, one space, and a nested indent matching the parent's content column.
 */
function addListItemRule(service: TurndownService): void {
  service.addRule('doc2mdListItem', {
    filter: 'li',
    replacement: (content, node) => {
      const parent = node.parentNode as HTMLElement | null;
      let prefix = '- ';
      if (parent?.nodeName === 'OL') {
        const start = Number(parent.getAttribute('start'));
        const index = Array.prototype.indexOf.call(parent.children, node);
        prefix = `${(Number.isFinite(start) && start ? start : 1) + index}. `;
      }
      const body = content
        .replace(/^\n+/, '')
        .replace(/\n+$/, '\n')
        .replace(/\n/gm, `\n${' '.repeat(prefix.length)}`);
      return prefix + body + (node.nextSibling && !/\n$/.test(body) ? '\n' : '');
    },
  });
}

function addImageRule(service: TurndownService): void {
  service.addRule('doc2mdImage', {
    filter: 'img',
    replacement: (_content, node) => {
      const element = node as HTMLElement;
      return `![image: ${element.getAttribute('src') || 'unnamed'}]`;
    },
  });
}

/**
 * mammoth renders a reference as `<sup><a href="#footnote-1" …>[1]</a></sup>`
 * and collects the bodies into a trailing `<ol>` of `<li id="footnote-1">`.
 * Both become standard Markdown footnote syntax.
 */
function addFootnoteRules(service: TurndownService): void {
  const noteNumber = (value: string | null): string | null => {
    const match = /^#?(?:footnote|endnote)(?:-ref)?-(\d+)$/.exec(value ?? '');
    return match ? match[1]! : null;
  };

  service.addRule('doc2mdFootnoteRef', {
    filter: (node) =>
      node.nodeName === 'SUP' &&
      noteNumber((node.firstChild as HTMLElement | null)?.getAttribute?.('href') ?? null) !==
        null,
    replacement: (_content, node) => {
      const href = (node.firstChild as HTMLElement).getAttribute('href');
      return `[^${noteNumber(href)}]`;
    },
  });

  // The "↑" link back to the reference is navigation, not content.
  service.addRule('doc2mdFootnoteBackLink', {
    filter: (node) =>
      node.nodeName === 'A' && noteNumber((node as HTMLElement).getAttribute('href')) !== null,
    replacement: (content, node) =>
      /-ref-\d+$/.test((node as HTMLElement).getAttribute('href') ?? '') ? '' : content,
  });

  service.addRule('doc2mdFootnoteBody', {
    filter: (node) =>
      node.nodeName === 'LI' && noteNumber((node as HTMLElement).getAttribute('id')) !== null,
    replacement: (content, node) => {
      const number = noteNumber((node as HTMLElement).getAttribute('id'));
      const text = content.replace(/\s+/g, ' ').trim();
      return text === '' ? '' : `\n[^${number}]: ${text}\n`;
    },
  });
}

/**
 * Replaces turndown-plugin-gfm's table support, which cannot flatten merged
 * cells. Reading the DOM directly also means the same renderer serves Word
 * tables and spreadsheets, so both look the same downstream.
 */
function addTableRule(service: TurndownService): void {
  service.addRule('doc2mdTable', {
    filter: 'table',
    replacement: (_content, node) => {
      const grid = tableToGrid(service, node as HTMLElement);
      const header = grid[0];
      if (!header) return '';
      const body = grid.slice(1);
      return `\n\n${renderTable(header, body, inferAlignments(body, header.length))}\n\n`;
    },
  });
}

/** Rows belonging to this table, skipping the rows of any nested table. */
function ownRows(table: HTMLElement): HTMLElement[] {
  const rows: HTMLElement[] = [];
  for (const child of Array.from(table.children)) {
    if (child.nodeName === 'TR') {
      rows.push(child as HTMLElement);
    } else if (['THEAD', 'TBODY', 'TFOOT'].includes(child.nodeName)) {
      for (const row of Array.from(child.children)) {
        if (row.nodeName === 'TR') rows.push(row as HTMLElement);
      }
    }
  }
  return rows;
}

/**
 * Expands `colspan` / `rowspan` into a plain rectangular grid, repeating the
 * merged value across every cell it covers. GFM has no notion of a span, and a
 * row that trails off into blanks is worse than one that repeats a label.
 */
function tableToGrid(service: TurndownService, table: HTMLElement): Grid {
  const rows = ownRows(table);
  const filled = new Map<string, string>();
  let width = 0;

  rows.forEach((row, r) => {
    let c = 0;
    for (const cell of Array.from(row.children)) {
      if (cell.nodeName !== 'TD' && cell.nodeName !== 'TH') continue;
      while (filled.has(`${r}:${c}`)) c++;

      const element = cell as HTMLElement;
      const text = cellMarkdown(service, element);
      const colspan = span(element, 'colspan');
      const rowspan = span(element, 'rowspan');
      for (let dr = 0; dr < rowspan; dr++) {
        for (let dc = 0; dc < colspan; dc++) filled.set(`${r + dr}:${c + dc}`, text);
      }
      c += colspan;
      width = Math.max(width, c);
    }
  });

  return rows.map((_row, r) =>
    Array.from({ length: width }, (_, c) => filled.get(`${r}:${c}`) ?? ''),
  );
}

function span(cell: HTMLElement, attribute: 'colspan' | 'rowspan'): number {
  const value = Number(cell.getAttribute(attribute));
  return Number.isFinite(value) && value > 1 ? Math.min(value, 1000) : 1;
}

/** A cell's contents as inline Markdown — bold, links and all. */
function cellMarkdown(service: TurndownService, cell: HTMLElement): string {
  return service.turndown(cell.innerHTML).replace(/\s*\n+\s*/g, ' ').trim();
}

// -------------------------------------------------------------------- output

function imageFooter(images: ImageRef[]): string {
  const lines = images.map((image) => {
    const alt = image.alt.trim();
    return `- \`${image.name}\` (${image.contentType})${alt ? ` — ${alt}` : ''}`;
  });
  return ['## Images', '', ...lines].join('\n');
}

/**
 * mammoth reports one message per unrecognised style, which for a heavily
 * styled document means dozens of near-identical lines. Show a few and count
 * the rest.
 */
function summariseMessages(messages: { type: string; message: string }[]): string[] {
  const distinct = [...new Set(messages.map((message) => message.message))];
  if (distinct.length === 0) return [];
  const shown = distinct.slice(0, MAX_REPORTED_WARNINGS);
  if (distinct.length > shown.length) {
    shown.push(`…and ${distinct.length - shown.length} more style warnings.`);
  }
  return shown;
}
