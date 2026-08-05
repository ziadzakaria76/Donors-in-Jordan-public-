import { beforeAll, describe, expect, it } from 'vitest';
import { convert } from '../src/converters/docx';
import { ConversionError, type ConversionResult } from '../src/core/types';
import { plainDocument, richDocument, tableOnlyDocument } from './docx-fixtures';

const run = (bytes: Uint8Array, name = 'document.docx'): Promise<ConversionResult> =>
  convert(new File([bytes as BlobPart], name), { fullExport: false });

describe('DOCX converter', () => {
  let rich: ConversionResult;

  beforeAll(async () => {
    rich = await run(await richDocument(), 'review.docx');
  });

  it('converts the whole document', () => {
    expect(rich.markdown).toMatchSnapshot();
  });

  it('reports no warnings for a well-formed document', () => {
    expect(rich.meta.warnings).toEqual([]);
  });

  it('maps Word heading styles to heading levels', () => {
    expect(rich.markdown).toContain('# Donor Landscape Review');
    expect(rich.markdown).toContain('## Executive summary');
    expect(rich.markdown).toContain('### Priority sectors');
  });

  it('keeps bold, italic and hyperlinks', () => {
    expect(rich.markdown).toContain('**18%**');
    expect(rich.markdown).toContain('*falling*');
    expect(rich.markdown).toContain('[portal listing](https://example.org/notices)');
  });

  it('preserves list nesting without padding every line', () => {
    expect(rich.markdown).toContain(
      ['- Water', '  - Rural supply', '    - Metering', '- Education'].join('\n'),
    );
    expect(rich.markdown).toContain(
      ['1. Submit the concept note', '   1. Attach the budget', '2. Await clearance'].join('\n'),
    );
  });

  it('maps a quote style to a block quote', () => {
    expect(rich.markdown).toContain('> The window closes at the end of the quarter.');
  });

  it('preserves document order', () => {
    const order = ['# Donor Landscape Review', '### Priority sectors', '- Water', '| Donor |'];
    const positions = order.map((needle) => rich.markdown.indexOf(needle));
    expect(positions.every((position) => position >= 0)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  });

  it('leaves headers and footers out of the body', () => {
    expect(rich.markdown).not.toContain('Confidential draft');
    expect(rich.markdown).not.toContain('Page 1');
  });

  it('preserves Arabic in logical order', () => {
    expect(rich.markdown).toContain('وزارة التخطيط والتعاون الدولي تعلن عن فرص جديدة');
  });
});

describe('DOCX converter — tables', () => {
  it('flattens merged cells by repeating the value', async () => {
    const { markdown } = await run(await richDocument());
    // rowSpan=2 on "World Bank", so it labels both of its rows.
    expect(markdown).toContain('| World Bank | Water | 250,000 |');
    expect(markdown).toContain('| World Bank | Education | 130,000 |');
    // columnSpan=2, repeated across both columns it covers.
    expect(markdown).toContain('| Total \\| all sectors | Total \\| all sectors | 380,000 |');
  });

  it('escapes a pipe inside a cell so the table survives', async () => {
    const { markdown } = await run(await richDocument());
    const row = markdown.split('\n').find((line) => line.includes('380,000'))!;
    expect(row.split(/(?<!\\)\|/).length).toBe(5);
  });

  it('right-aligns a numeric column', async () => {
    const { markdown } = await run(await richDocument());
    expect(markdown).toContain('| --- | --- | ---: |');
  });

  it('emits a table-only document with nothing prepended', async () => {
    const { markdown } = await run(await tableOnlyDocument());
    expect(markdown).toBe(
      ['| Ref | Amount |', '| --- | ---: |', '| A-1 | 1200 |'].join('\n'),
    );
  });
});

describe('DOCX converter — footnotes', () => {
  it('puts markers inline and definitions at the end', async () => {
    const { markdown } = await run(await richDocument());
    expect(markdown).toContain('against a *falling* baseline[^1].');
    expect(markdown).toContain('[^1]: Figures are provisional pending audit.');
    expect(markdown).toContain('[^2]: Converted at the 2026 average rate.');
    expect(markdown.indexOf('[^1]:')).toBeGreaterThan(markdown.indexOf('baseline[^1]'));
  });

  it('drops the back-links, which are navigation rather than content', async () => {
    const { markdown } = await run(await richDocument());
    expect(markdown).not.toContain('↑');
  });
});

describe('DOCX converter — images', () => {
  it('replaces the image with a placeholder and never embeds bytes', async () => {
    const { markdown, meta } = await run(await richDocument());
    expect(markdown).toContain('![image: image-1.png]');
    expect(markdown).not.toContain('data:image');
    expect(markdown).not.toContain('base64');
    expect(meta.images).toEqual(['image-1.png']);
  });

  it('lists images in a footer section with their alt text', async () => {
    const { markdown } = await run(await richDocument());
    expect(markdown).toContain('## Images');
    expect(markdown).toContain('- `image-1.png` (image/png) — Funding by sector');
  });

  it('omits the footer entirely when there are no images', async () => {
    const { markdown, meta } = await run(await plainDocument());
    expect(markdown).not.toContain('## Images');
    expect(meta.images).toEqual([]);
  });
});

describe('DOCX converter — edge cases', () => {
  it('converts a minimal document without stray artefacts', async () => {
    const { markdown } = await run(await plainDocument(), 'notes.docx');
    // mammoth always appends an empty <ol> and <dl> for notes and comments;
    // neither may leak into the output.
    expect(markdown).toBe('# Notes\n\nA single paragraph of body text.');
  });

  it('explains an unreadable file instead of leaking a stack trace', async () => {
    const notADocx = new File([new Uint8Array([1, 2, 3, 4])], 'broken.docx');
    await expect(convert(notADocx, { fullExport: false })).rejects.toBeInstanceOf(
      ConversionError,
    );
    await expect(convert(notADocx, { fullExport: false })).rejects.toThrow(
      /password-protected, corrupt, or not a real/,
    );
  });

  it('reports progress from start to finish', async () => {
    const seen: number[] = [];
    await convert(new File([(await plainDocument()) as BlobPart], 'notes.docx'), {
      fullExport: false,
      onProgress: (fraction) => seen.push(fraction),
    });
    expect(seen[0]).toBeLessThan(1);
    expect(seen.at(-1)).toBe(1);
    expect([...seen].sort((a, b) => a - b)).toEqual(seen);
  });
});
