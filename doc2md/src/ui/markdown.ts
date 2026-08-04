/**
 * A small GFM-subset renderer for the preview pane.
 *
 * It only has to render Markdown that Doc2MD itself produced, so it covers
 * headings, lists, GFM tables, code, block quotes, emphasis, links, YAML
 * front-matter and HTML comments — and nothing else. That is a few hundred
 * bytes against ~40 KB for a full parser, and it keeps the initial bundle
 * inside budget.
 *
 * All input is escaped before any markup is inserted, so a document that
 * contains raw HTML renders as text rather than executing.
 */

export function renderMarkdown(source: string): string {
  const lines = source.replace(/\r\n?/g, '\n').split('\n');
  const out: string[] = [];
  let i = 0;

  // YAML front-matter, rendered as a muted header block rather than a rule
  // followed by stray text.
  if (lines[0]?.trim() === '---') {
    const close = lines.indexOf('---', 1);
    if (close > 0) {
      out.push(
        `<pre class="mb-4 overflow-x-auto rounded-lg border border-slate-200 bg-slate-100/70 p-3 text-xs opacity-80 dark:border-white/10 dark:bg-white/5">` +
          escapeHtml(lines.slice(1, close).join('\n')) +
          `</pre>`,
      );
      i = close + 1;
    }
  }

  out.push(renderBlocks(lines, i, lines.length));
  return out.join('');
}

function renderBlocks(lines: string[], from: number, to: number): string {
  const out: string[] = [];
  let paragraph: string[] = [];

  const flush = (): void => {
    if (paragraph.length === 0) return;
    out.push(`<p>${inline(paragraph.join(' '))}</p>`);
    paragraph = [];
  };

  let i = from;
  while (i < to) {
    const line = lines[i]!;
    const trimmed = line.trim();

    if (trimmed === '') {
      flush();
      i++;
      continue;
    }

    // Fenced code.
    const fence = /^(`{3,}|~{3,})\s*([\w-]*)\s*$/.exec(trimmed);
    if (fence) {
      flush();
      const marker = fence[1]!;
      const body: string[] = [];
      i++;
      while (i < to && !lines[i]!.trim().startsWith(marker)) body.push(lines[i]!), i++;
      i++; // closing fence
      const lang = fence[2] ? ` class="language-${escapeHtml(fence[2])}"` : '';
      out.push(`<pre><code${lang}>${escapeHtml(body.join('\n'))}</code></pre>`);
      continue;
    }

    // HTML comments — Doc2MD uses them for truncation and OCR notes, so they
    // should be visible but obviously not part of the document text.
    if (trimmed.startsWith('<!--')) {
      flush();
      const body: string[] = [trimmed];
      while (i < to && !lines[i]!.includes('-->')) i++, body.push(lines[i] ?? '');
      i++;
      const text = body.join(' ').replace(/^<!--\s*/, '').replace(/\s*-->.*$/, '');
      out.push(
        `<div class="my-2 text-xs italic opacity-60">${escapeHtml(text)}</div>`,
      );
      continue;
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (heading) {
      flush();
      const level = heading[1]!.length;
      out.push(`<h${level}>${inline(heading[2]!.replace(/\s+#+$/, ''))}</h${level}>`);
      i++;
      continue;
    }

    if (/^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$/.test(trimmed)) {
      flush();
      out.push('<hr />');
      i++;
      continue;
    }

    if (trimmed.startsWith('>')) {
      flush();
      const body: string[] = [];
      while (i < to && (lines[i]!.trim().startsWith('>') || lines[i]!.trim() !== '')) {
        if (!lines[i]!.trim().startsWith('>')) break;
        body.push(lines[i]!.replace(/^\s*>\s?/, ''));
        i++;
      }
      out.push(`<blockquote>${renderBlocks(body, 0, body.length)}</blockquote>`);
      continue;
    }

    // GFM table: a header row followed by a delimiter row.
    if (trimmed.includes('|') && isDelimiterRow(lines[i + 1])) {
      flush();
      const header = splitRow(trimmed);
      const aligns = splitRow(lines[i + 1]!.trim()).map(alignOf);
      i += 2;
      const rows: string[][] = [];
      while (i < to && lines[i]!.trim().includes('|') && lines[i]!.trim() !== '') {
        rows.push(splitRow(lines[i]!.trim()));
        i++;
      }
      out.push(renderTable(header, aligns, rows));
      continue;
    }

    const bullet = listMarker(line);
    if (bullet) {
      flush();
      const [html, next] = renderList(lines, i, to, bullet.indent);
      out.push(html);
      i = next;
      continue;
    }

    paragraph.push(trimmed);
    i++;
  }

  flush();
  return out.join('');
}

interface Marker {
  indent: number;
  ordered: boolean;
  start: number;
  content: string;
}

function listMarker(line: string): Marker | null {
  const m = /^(\s*)(?:([-*+])|(\d{1,9})[.)])\s+(.*)$/.exec(line);
  if (!m) return null;
  return {
    indent: m[1]!.replace(/\t/g, '    ').length,
    ordered: m[3] !== undefined,
    start: m[3] ? Number(m[3]) : 1,
    content: m[4]!,
  };
}

/** Renders one list level, recursing for anything indented further. */
function renderList(
  lines: string[],
  from: number,
  to: number,
  indent: number,
): [string, number] {
  const first = listMarker(lines[from]!)!;
  const tag = first.ordered ? 'ol' : 'ul';
  const items: string[] = [];
  let i = from;

  while (i < to) {
    const line = lines[i]!;
    if (line.trim() === '') {
      // A blank line only ends the list if the next line is not a deeper or
      // equal continuation of it.
      const next = lines[i + 1];
      if (next === undefined) break;
      const nextMarker = listMarker(next);
      if (!nextMarker || nextMarker.indent < indent) break;
      i++;
      continue;
    }
    const marker = listMarker(line);
    if (!marker || marker.indent < indent) break;

    if (marker.indent > indent) {
      const [nested, next] = renderList(lines, i, to, marker.indent);
      if (items.length > 0) items[items.length - 1] += nested;
      else items.push(nested);
      i = next;
      continue;
    }

    if (marker.ordered !== first.ordered) break;

    // Lazy continuation lines belong to the item they follow.
    const body: string[] = [marker.content];
    i++;
    while (i < to) {
      const cont = lines[i]!;
      if (cont.trim() === '' || listMarker(cont)) break;
      const contIndent = cont.replace(/\t/g, '    ').search(/\S/);
      if (contIndent <= indent) break;
      body.push(cont.trim());
      i++;
    }
    items.push(`<li>${inline(body.join(' '))}`);
  }

  const startAttr = first.ordered && first.start !== 1 ? ` start="${first.start}"` : '';
  return [`<${tag}${startAttr}>${items.map((it) => `${it}</li>`).join('')}</${tag}>`, i];
}

function isDelimiterRow(line: string | undefined): boolean {
  if (!line) return false;
  const t = line.trim();
  return t.includes('|') && /^\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?$/.test(t);
}

function splitRow(row: string): string[] {
  let t = row.trim();
  if (t.startsWith('|')) t = t.slice(1);
  if (t.endsWith('|') && !t.endsWith('\\|')) t = t.slice(0, -1);
  // Split on unescaped pipes only, so `\|` inside a cell survives.
  return t
    .split(/(?<!\\)\|/)
    .map((cell) => cell.trim().replace(/\\\|/g, '|'));
}

function alignOf(spec: string): string {
  const left = spec.startsWith(':');
  const right = spec.endsWith(':');
  if (left && right) return ' style="text-align:center"';
  if (right) return ' style="text-align:right"';
  return '';
}

function renderTable(header: string[], aligns: string[], rows: string[][]): string {
  const th = header
    .map((cell, n) => `<th${aligns[n] ?? ''}>${inline(cell)}</th>`)
    .join('');
  const body = rows
    .map((row) => {
      // Pad or clip so a ragged row cannot break the table layout.
      const cells = Array.from(
        { length: header.length },
        (_, n) => `<td${aligns[n] ?? ''}>${inline(row[n] ?? '')}</td>`,
      );
      return `<tr>${cells.join('')}</tr>`;
    })
    .join('');
  return `<div class="table-scroll"><table><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// ------------------------------------------------------------------- inline

function inline(source: string): string {
  let out = '';
  let cursor = 0;
  const code = /`([^`\n]+)`/g;
  let match: RegExpExecArray | null;
  while ((match = code.exec(source)) !== null) {
    out += emphasis(source.slice(cursor, match.index));
    out += `<code>${escapeHtml(match[1]!)}</code>`;
    cursor = match.index + match[0].length;
  }
  return out + emphasis(source.slice(cursor));
}

/** Input is escaped first, so every replacement below inserts trusted markup. */
function emphasis(raw: string): string {
  let s = escapeHtml(raw);
  s = s.replace(
    /!\[([^\]]*)\]\([^)]*\)/g,
    (_, alt: string) => `<em class="opacity-70">${alt || 'image'}</em>`,
  );
  s = s.replace(
    /\[([^\]]+)\]\(([^)\s]+)(?:\s[^)]*)?\)/g,
    (whole: string, text: string, href: string) =>
      isSafeHref(href)
        ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`
        : whole,
  );
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_\n]+)__/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*\w])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  s = s.replace(/(^|[^_\w])_([^_\n]+)_/g, '$1<em>$2</em>');
  s = s.replace(/~~([^~\n]+)~~/g, '<del>$1</del>');
  s = s.replace(/ {2,}$/, '<br />');
  return s;
}

function isSafeHref(href: string): boolean {
  const value = href.trim().toLowerCase();
  if (value.startsWith('#') || value.startsWith('/') || value.startsWith('./')) return true;
  return /^(https?:|mailto:|tel:)/.test(value);
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
