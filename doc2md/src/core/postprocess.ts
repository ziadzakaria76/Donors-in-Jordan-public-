import type { ConversionMeta, SourceKind } from './types';

/**
 * The shared pass every converter's output goes through: strip what wastes
 * tokens, normalise what a model reads differently from a human, and prepend
 * front-matter describing where the document came from.
 */

/**
 * Rough token estimate. Four characters per token is the usual back-of-envelope
 * figure for English prose and is close enough to be useful as a live counter.
 */
export function estimateTokens(markdown: string): number {
  return Math.ceil(markdown.length / 4);
}

export function countWords(markdown: string): number {
  const words = markdown.trim().match(/\S+/g);
  return words ? words.length : 0;
}

/**
 * Invisible characters that carry no meaning: zero-width space, soft hyphen and
 * a stray byte-order mark.
 *
 * Deliberately *not* included are U+200C and U+200D. They are zero-width too,
 * but the zero-width non-joiner and joiner change how Arabic, Persian and many
 * Indic scripts render and, in some words, what they mean — stripping every
 * zero-width character alike would quietly corrupt them.
 */
const INVISIBLE = /[\u200B\u00AD\uFEFF]/g;

/** C0 and C1 controls, keeping the newlines and tabs that are real layout. */
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g;

/** Typographic characters replaced by their ASCII equivalents. */
const PUNCTUATION: [RegExp, string][] = [
  [/[‘’‚‛′]/g, "'"],
  [/[“”„‟″]/g, '"'],
  [/\u2014/g, '--'],
  [/[–‒―]/g, '-'],
  [/\u2026/g, '...'],
  [/\u00A0/g, ' '],
  [/[\u2000-\u200A\u202F\u205F\u3000]/g, ' '],
];

/** A heading with no text after the hashes. */
const EMPTY_HEADING = /^ {0,3}#{1,6} *$/;

/** A table row whose every cell is empty. The delimiter row has dashes in it. */
const EMPTY_TABLE_ROW = /^ *\|(?: *\|)+ *$/;

export interface FinalizeInput {
  filename: string;
  kind: SourceKind | null;
  markdown: string;
  meta: ConversionMeta;
  /** Injected so the front-matter date is deterministic under test. */
  now?: Date;
}

/**
 * Applies the token-efficiency pass and prepends YAML front-matter. This is the
 * last thing to touch the Markdown before the user sees it.
 */
export function finalize(input: FinalizeInput): string {
  const body = tidy(input.markdown);
  const header = frontMatter(input, body);
  return body === '' ? header : `${header}\n${body}\n`;
}

/** The token-efficiency pass, on its own so it can be tested directly. */
export function tidy(markdown: string): string {
  const segments = splitFencedCode(markdown.replace(/\r\n?/g, '\n'));
  const cleaned = segments.map((segment) =>
    // A fenced block is quoted text: its whitespace, quotes and dashes are
    // content, and rewriting them would change what the block says.
    segment.code ? segment.text : tidyProse(segment.text),
  );

  return (
    cleaned
      .join('')
      // At most one blank line anywhere. Converters emit generous spacing to
      // keep blocks apart; the model does not need three of them.
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  );
}

function tidyProse(text: string): string {
  let out = text.replace(INVISIBLE, '').replace(CONTROL, '');
  out = normalisePunctuation(out);
  return out
    .split('\n')
    .map((line) => line.replace(/[ \t]+$/, ''))
    .filter((line) => !EMPTY_HEADING.test(line) && !EMPTY_TABLE_ROW.test(line))
    .join('\n');
}

/**
 * Rewrites typographic punctuation outside inline code. `--flag` in a code span
 * must survive, and so must a quoted string in a sample command.
 */
function normalisePunctuation(text: string): string {
  let out = '';
  let cursor = 0;
  const span = /`+[^`\n]*`+/g;
  let match: RegExpExecArray | null;
  while ((match = span.exec(text)) !== null) {
    out += replaceAll(text.slice(cursor, match.index));
    out += match[0];
    cursor = match.index + match[0].length;
  }
  return out + replaceAll(text.slice(cursor));
}

function replaceAll(text: string): string {
  let out = text;
  for (const [pattern, replacement] of PUNCTUATION) out = out.replace(pattern, replacement);
  return out;
}

interface Segment {
  code: boolean;
  text: string;
}

/** Splits on fenced code blocks, keeping the fences with the code. */
function splitFencedCode(markdown: string): Segment[] {
  const segments: Segment[] = [];
  const lines = markdown.split('\n');
  let buffer: string[] = [];
  let fence: string | null = null;

  const flush = (code: boolean): void => {
    if (buffer.length === 0) return;
    segments.push({ code, text: buffer.join('\n') });
    buffer = [];
  };

  for (const line of lines) {
    const opener = /^ {0,3}(`{3,}|~{3,})/.exec(line);
    if (fence === null) {
      if (opener) {
        // Keep the newline that separated this from the prose before it.
        flush(false);
        fence = opener[1]!;
        buffer.push(line);
      } else {
        buffer.push(line);
      }
      continue;
    }
    buffer.push(line);
    if (opener && opener[1]![0] === fence[0] && opener[1]!.length >= fence.length) {
      flush(true);
      fence = null;
    }
  }
  // An unterminated fence is still code as far as the author was concerned.
  flush(fence !== null);

  // join('') would lose the newline between segments, so put it back.
  return segments.map((segment, index) => ({
    ...segment,
    text: index < segments.length - 1 ? `${segment.text}\n` : segment.text,
  }));
}

// ------------------------------------------------------------- front matter

function frontMatter(input: FinalizeInput, body: string): string {
  const lines = [`source: ${yamlScalar(input.filename)}`];
  if (input.kind) lines.push(`type: ${input.kind}`);
  if (input.meta.pages !== undefined) lines.push(`pages: ${input.meta.pages}`);
  if (input.meta.sheets !== undefined && input.meta.sheets.length > 0) {
    lines.push(`sheets: [${input.meta.sheets.map(yamlScalar).join(', ')}]`);
  }
  if (input.meta.images !== undefined && input.meta.images.length > 0) {
    lines.push(`images: ${input.meta.images.length}`);
  }
  lines.push(`converted: ${isoDate(input.now ?? new Date())}`);
  lines.push(`words: ${countWords(body)}`);
  return ['---', ...lines, '---'].join('\n');
}

/** The local calendar date — "when I converted it", not a UTC instant. */
function isoDate(date: Date): string {
  const pad = (value: number): string => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Characters YAML reads as an indicator when they open a scalar. */
const YAML_LEADING_INDICATOR = /^[-?:,[\]{}#&*!|>'"%@`]/;

/**
 * Quotes a YAML scalar when it would otherwise be misread — filenames routinely
 * contain colons, commas and brackets, and sheet names can be anything.
 *
 * Stated as a denylist of the characters YAML actually treats as syntax rather
 * than an allowlist of safe ones: an allowlist has to enumerate every script
 * that may appear in a sheet name, and quietly quotes Arabic when it does not.
 */
function yamlScalar(value: string): string {
  const plain =
    value !== '' &&
    value === value.trim() &&
    !YAML_LEADING_INDICATOR.test(value) &&
    // ": " and " #" end a plain scalar; the rest are flow-context syntax, and
    // sheet names are emitted inside a flow sequence.
    !/: | #|[:,[\]{}"']/.test(value);
  if (plain) return value;
  return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}
