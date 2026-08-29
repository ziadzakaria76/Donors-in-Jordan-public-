import { describe, expect, it } from 'vitest';
import { renderMarkdown } from '../src/ui/markdown';

describe('renderMarkdown', () => {
  it('renders headings and paragraphs, joining wrapped lines', () => {
    const html = renderMarkdown('# Title\n\nOne line\nand its continuation.');
    expect(html).toContain('<h1 dir="auto">Title</h1>');
    expect(html).toContain('<p dir="auto">One line and its continuation.</p>');
  });

  it('renders a GFM table with alignment and pads ragged rows', () => {
    const html = renderMarkdown(
      ['| A | B |', '| --- | ---: |', '| 1 | 2 |', '| 3 |'].join('\n'),
    );
    expect(html).toContain('<th dir="auto">A</th>');
    expect(html).toContain('<th dir="auto" style="text-align:right">B</th>');
    expect(html).toContain('<td dir="auto">1</td>');
    // The short row still closes with the right number of cells.
    expect(html).toContain(
      '<tr><td dir="auto">3</td><td dir="auto" style="text-align:right"></td></tr>',
    );
  });

  it('nests lists by indentation', () => {
    const html = renderMarkdown('- one\n  - inner\n- two');
    expect(html).toBe(
      '<ul><li dir="auto">one<ul><li dir="auto">inner</li></ul></li><li dir="auto">two</li></ul>',
    );
  });

  it('keeps ordered lists ordered and honours a non-1 start', () => {
    expect(renderMarkdown('3. c\n4. d')).toBe(
      '<ol start="3"><li dir="auto">c</li><li dir="auto">d</li></ol>',
    );
  });

  it('escapes HTML rather than executing it', () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">');
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
  });

  it('refuses javascript: links but keeps the label', () => {
    const html = renderMarkdown('[click](javascript:alert(1))');
    expect(html).not.toContain('href="javascript');
    expect(html).toContain('click');
  });

  it('leaves emphasis markers inside code spans alone', () => {
    expect(renderMarkdown('`a * b * c`')).toBe('<p dir="auto"><code>a * b * c</code></p>');
  });

  it('shows front-matter as a block instead of a horizontal rule', () => {
    const html = renderMarkdown('---\nsource: a.pdf\n---\n\nBody');
    expect(html).toContain('source: a.pdf');
    expect(html).not.toContain('<hr');
    expect(html).toContain('<p dir="auto">Body</p>');
  });

  it('surfaces HTML comments as visible notes', () => {
    expect(renderMarkdown('<!-- truncated: 900 rows total -->')).toContain(
      'truncated: 900 rows total',
    );
  });

  it('marks every text block dir="auto" so a mixed-direction table is readable', () => {
    // Without per-cell isolation the bidi algorithm reorders an Arabic cell
    // against its LTR neighbours and the columns appear to swap.
    const html = renderMarkdown(
      ['| Donor | Sector | Value |', '| --- | --- | ---: |', '| World Bank | التعليم | 130000 |'].join('\n'),
    );
    expect(html).toContain('<td dir="auto">World Bank</td>');
    expect(html).toContain('<td dir="auto">التعليم</td>');
    expect(html).toContain('<td dir="auto" style="text-align:right">130000</td>');
  });

  it('preserves Arabic text without reordering it', () => {
    const arabic = 'وزارة التخطيط والتعاون الدولي';
    expect(renderMarkdown(`## ${arabic}`)).toBe(`<h2 dir="auto">${arabic}</h2>`);
  });
});
