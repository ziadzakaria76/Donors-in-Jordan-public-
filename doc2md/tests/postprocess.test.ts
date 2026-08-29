import { describe, expect, it } from 'vitest';
import { countWords, estimateTokens, finalize, tidy } from '../src/core/postprocess';

const NOW = new Date(2026, 7, 5); // 5 August 2026, local time

describe('tidy — whitespace', () => {
  it('collapses runs of blank lines to one', () => {
    expect(tidy('a\n\n\n\n\nb')).toBe('a\n\nb');
  });

  it('strips trailing whitespace from every line', () => {
    expect(tidy('a   \nb\t\t\nc')).toBe('a\nb\nc');
  });

  it('trims leading and trailing blank lines', () => {
    expect(tidy('\n\n  text  \n\n\n')).toBe('text');
  });

  it('normalises CRLF', () => {
    expect(tidy('a\r\nb\rc')).toBe('a\nb\nc');
  });
});

describe('tidy — invisible characters', () => {
  it('removes zero-width spaces, soft hyphens and stray BOMs', () => {
    expect(tidy('a​b­c﻿d')).toBe('abcd');
  });

  it('removes control characters but keeps newlines and tabs', () => {
    expect(tidy('abc')).toBe('abc');
    expect(tidy('a\tb\nc')).toBe('a\tb\nc');
  });

  it('keeps the zero-width joiners that Arabic and Persian need', () => {
    // U+200C and U+200D are zero-width but change what the word says.
    const persian = 'می‌رود';
    expect(tidy(persian)).toBe(persian);
    expect(tidy('a‍b')).toBe('a‍b');
  });
});

describe('tidy — punctuation', () => {
  it('folds smart quotes to ASCII', () => {
    expect(tidy('“quoted” and ‘single’')).toBe('"quoted" and \'single\'');
  });

  it('folds dashes and ellipses', () => {
    expect(tidy('a—b')).toBe('a--b');
    expect(tidy('2020–2026')).toBe('2020-2026');
    expect(tidy('wait…')).toBe('wait...');
  });

  it('folds exotic spaces to a plain space', () => {
    expect(tidy('a b c　d')).toBe('a b c d');
  });

  it('leaves Arabic punctuation alone', () => {
    const arabic = 'وزارة، التخطيط؛ والتعاون؟';
    expect(tidy(arabic)).toBe(arabic);
  });

  it('does not rewrite punctuation inside an inline code span', () => {
    expect(tidy('use `--flag` here—yes')).toBe('use `--flag` here--yes');
    expect(tidy('`“literal”`')).toBe('`“literal”`');
  });

  it('leaves a fenced code block untouched', () => {
    const source = ['before—here', '', '```', 'a — b   ', '   ', '```', '', 'after'].join('\n');
    const result = tidy(source);
    expect(result).toContain('```\na — b   \n   \n```');
    expect(result).toContain('before--here');
  });
});

describe('tidy — empty structure', () => {
  it('removes headings with no text', () => {
    expect(tidy('# Real\n\n##\n\nBody')).toBe('# Real\n\nBody');
  });

  it('removes table rows whose cells are all empty', () => {
    const table = ['| A | B |', '| --- | --- |', '| 1 | 2 |', '|  |  |', '| 3 | 4 |'].join('\n');
    expect(tidy(table)).toBe(
      ['| A | B |', '| --- | --- |', '| 1 | 2 |', '| 3 | 4 |'].join('\n'),
    );
  });

  it('keeps the delimiter row, which looks empty-ish but is not', () => {
    expect(tidy('| A |\n| --- |\n| 1 |')).toContain('| --- |');
  });

  it('keeps a row that has any content at all', () => {
    expect(tidy('| A | B |\n| --- | --- |\n|  | 2 |')).toContain('|  | 2 |');
  });
});

describe('countWords and estimateTokens', () => {
  it('counts words, not characters', () => {
    expect(countWords('one two  three\nfour')).toBe(4);
    expect(countWords('   ')).toBe(0);
  });

  it('estimates tokens at four characters each', () => {
    expect(estimateTokens('abcd')).toBe(1);
    expect(estimateTokens('abcde')).toBe(2);
    expect(estimateTokens('')).toBe(0);
  });
});

describe('finalize — front matter', () => {
  it('describes a PDF', () => {
    const output = finalize({
      filename: 'review.pdf',
      kind: 'pdf',
      markdown: '# Title\n\nTwo words.',
      meta: { pages: 12, warnings: [] },
      now: NOW,
    });
    expect(output).toBe(
      [
        '---',
        'source: review.pdf',
        'type: pdf',
        'pages: 12',
        'converted: 2026-08-05',
        'words: 4',
        '---',
        '# Title',
        '',
        'Two words.',
        '',
      ].join('\n'),
    );
  });

  it('lists sheet names for a workbook', () => {
    const output = finalize({
      filename: 'budget.xlsx',
      kind: 'xlsx',
      markdown: 'body',
      meta: { sheets: ['Orders', 'المانحون'], warnings: [] },
      now: NOW,
    });
    expect(output).toContain('sheets: [Orders, المانحون]');
    expect(output).not.toContain('pages:');
  });

  it('counts images rather than listing them', () => {
    const output = finalize({
      filename: 'report.docx',
      kind: 'docx',
      markdown: 'body',
      meta: { images: ['image-1.png', 'image-2.png'], warnings: [] },
      now: NOW,
    });
    expect(output).toContain('images: 2');
  });

  it('omits sections that do not apply', () => {
    const output = finalize({
      filename: 'notes.csv',
      kind: 'csv',
      markdown: 'body',
      meta: { warnings: [], sheets: [], images: [] },
      now: NOW,
    });
    expect(output).not.toContain('sheets:');
    expect(output).not.toContain('images:');
    expect(output).not.toContain('pages:');
  });

  it('quotes a filename that would otherwise change what the YAML means', () => {
    for (const [filename, expected] of [
      ['Q3: budget.xlsx', '"Q3: budget.xlsx"'],
      ['a, b.csv', '"a, b.csv"'],
      ['[draft].pdf', '"[draft].pdf"'],
      ['say "hi".docx', '"say \\"hi\\".docx"'],
      [' leading.pdf', '" leading.pdf"'],
    ] as const) {
      const output = finalize({
        filename,
        kind: null,
        markdown: 'body',
        meta: { warnings: [] },
        now: NOW,
      });
      expect(output, filename).toContain(`source: ${expected}`);
    }
  });

  it('leaves an ordinary filename unquoted', () => {
    const output = finalize({
      filename: 'donor-review (final).pdf',
      kind: 'pdf',
      markdown: 'body',
      meta: { warnings: [] },
      now: NOW,
    });
    expect(output).toContain('source: donor-review (final).pdf');
  });

  it('counts the words of the tidied body, not the front matter', () => {
    const output = finalize({
      filename: 'a.csv',
      kind: 'csv',
      markdown: 'one two three\n\n\n\nfour',
      meta: { warnings: [] },
      now: NOW,
    });
    expect(output).toContain('words: 4');
  });

  it('still produces front matter for an empty conversion', () => {
    const output = finalize({
      filename: 'blank.csv',
      kind: 'csv',
      markdown: '   \n\n',
      meta: { warnings: [] },
      now: NOW,
    });
    expect(output).toBe(
      ['---', 'source: blank.csv', 'type: csv', 'converted: 2026-08-05', 'words: 0', '---'].join(
        '\n',
      ),
    );
  });

  it('produces front matter a YAML parser reads back correctly', () => {
    const output = finalize({
      filename: 'Q3: budget.xlsx',
      kind: 'xlsx',
      markdown: 'body',
      meta: { sheets: ['Orders'], warnings: [] },
      now: NOW,
    });
    const block = output.split('---')[1]!;
    const parsed = Object.fromEntries(
      block
        .trim()
        .split('\n')
        .map((line) => {
          const at = line.indexOf(': ');
          return [line.slice(0, at), line.slice(at + 2)];
        }),
    );
    expect(parsed['source']).toBe('"Q3: budget.xlsx"');
    expect(parsed['type']).toBe('xlsx');
    expect(parsed['converted']).toBe('2026-08-05');
  });
});
