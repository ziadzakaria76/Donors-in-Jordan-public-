import { beforeAll, describe, expect, it } from 'vitest';
import { convert } from '../src/converters/pdf';
import { ConversionError, type ConversionResult } from '../src/core/types';
import { ambiguousPdf, ARABIC_LINES, reportPdf, scannedPdf, simplePdf } from './pdf-fixtures';

const run = (bytes: Uint8Array, name = 'document.pdf'): Promise<ConversionResult> =>
  convert(new File([bytes as BlobPart], name), { fullExport: false });

describe('PDF converter', () => {
  let report: ConversionResult;

  beforeAll(async () => {
    report = await run(reportPdf(), 'review.pdf');
  }, 30_000);

  it('converts the whole report', () => {
    expect(report.markdown).toMatchSnapshot();
  });

  it('counts the pages', () => {
    expect(report.meta.pages).toBe(3);
  });

  it('infers a heading hierarchy from relative font size', () => {
    expect(report.markdown).toContain('# Donor Landscape Review');
    expect(report.markdown).toContain('## Executive summary');
    expect(report.markdown).toContain('### Priority sectors');
  });

  it('rejoins wrapped lines into one paragraph', () => {
    expect(report.markdown).toContain(
      'Funding across the reviewed portals rose sharply over the period under review, ' +
        'with the largest single increase recorded in the water sector, where three new ' +
        'facilities were announced.',
    );
  });

  it('keeps a real paragraph break', () => {
    expect(report.markdown).toContain('\n\nA second paragraph starts here and stops short.');
  });

  it('rebuilds bulleted and numbered lists, with nesting', () => {
    expect(report.markdown).toContain(
      ['- Water and sanitation', '- Education', '  - Vocational training'].join('\n'),
    );
    expect(report.markdown).toContain('1. Submit the concept note\n2. Await clearance');
  });

  it('detects a table from aligned columns', () => {
    expect(report.markdown).toContain(
      [
        '| Donor | Sector | Value |',
        '| --- | --- | ---: |',
        '| World Bank | Water | 250,000 |',
        '| EBRD | Transport | 410,000 |',
        '| IsDB | Education | 130,000 |',
      ].join('\n'),
    );
  });

  it('strips the running head and foot from every page', () => {
    expect(report.markdown).not.toContain('Ministry of Planning');
    expect(report.markdown).not.toContain('Page 1 of 3');
    expect(report.meta.warnings).toContain(
      'Removed 2 repeating header/footer line(s) found on most pages.',
    );
  });

  it('drops a page that held nothing but furniture, without an OCR note', () => {
    // Page 3 had a text layer; it just had no content of its own.
    expect(report.markdown).not.toContain('OCR needed');
  });

  it('returns Arabic in logical order, not reversed', () => {
    for (const line of ARABIC_LINES) expect(report.markdown).toContain(line);
    // The reversed form is what a naive left-to-right read would produce.
    const reversed = [...ARABIC_LINES[0]!].reverse().join('');
    expect(report.markdown).not.toContain(reversed);
  });
});

describe('PDF converter — pages without text', () => {
  it('marks every scanned page instead of dropping it', async () => {
    const { markdown, meta } = await run(scannedPdf(), 'scan.pdf');
    expect(markdown).toBe(
      '<!-- page 1: no text layer, OCR needed -->\n\n<!-- page 2: no text layer, OCR needed -->',
    );
    expect(meta.warnings).toEqual([
      'No page in this PDF has a text layer — it is a scan and needs OCR.',
    ]);
  });
});

describe('PDF converter — ambiguity', () => {
  it('falls back to plain text when columns do not line up', async () => {
    const { markdown } = await run(ambiguousPdf(), 'ambiguous.pdf');
    expect(markdown).not.toContain('|');
    expect(markdown).toContain('# Ambiguous layout');
    expect(markdown).toContain('A line with no second column at all');
  });
});

describe('PDF converter — edge cases', () => {
  it('converts the simplest possible document', async () => {
    const { markdown, meta } = await run(simplePdf(), 'notes.pdf');
    expect(markdown).toBe('# Field Notes\n\nA single paragraph of body text.');
    expect(meta.pages).toBe(1);
    expect(meta.warnings).toEqual([]);
  });

  it('explains an unreadable file instead of leaking a stack trace', async () => {
    const notAPdf = new File([new Uint8Array([1, 2, 3, 4])], 'broken.pdf');
    await expect(convert(notAPdf, { fullExport: false })).rejects.toBeInstanceOf(
      ConversionError,
    );
    await expect(convert(notAPdf, { fullExport: false })).rejects.toThrow(
      /password-protected or corrupt/,
    );
  });

  it('reports progress from start to finish', async () => {
    const seen: number[] = [];
    await convert(new File([simplePdf() as BlobPart], 'notes.pdf'), {
      fullExport: false,
      onProgress: (fraction) => seen.push(fraction),
    });
    expect(seen[0]).toBeLessThan(1);
    expect(seen.at(-1)).toBe(1);
    expect([...seen].sort((a, b) => a - b)).toEqual(seen);
  });
});
