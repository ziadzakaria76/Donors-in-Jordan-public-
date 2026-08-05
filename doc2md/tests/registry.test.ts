import { describe, expect, it } from 'vitest';
import { formatBytes, kindFor, MAX_FILE_BYTES, rejectionReason } from '../src/core/registry';

const fileOf = (name: string, size = 10): File =>
  new File([new Uint8Array(size)], name);

describe('kindFor', () => {
  it('maps every accepted extension, case-insensitively', () => {
    expect(kindFor(fileOf('a.pdf'))).toBe('pdf');
    expect(kindFor(fileOf('a.DOCX'))).toBe('docx');
    expect(kindFor(fileOf('a.xlsx'))).toBe('xlsx');
    expect(kindFor(fileOf('a.xlsm'))).toBe('xlsx');
    expect(kindFor(fileOf('a.csv'))).toBe('csv');
  });

  it('is null for anything else', () => {
    expect(kindFor(fileOf('a.doc'))).toBeNull();
    expect(kindFor(fileOf('noextension'))).toBeNull();
  });
});

describe('rejectionReason', () => {
  it('accepts a normal file', () => {
    expect(rejectionReason(fileOf('report.xlsx'))).toBeNull();
  });

  it('explains legacy Office formats instead of just refusing them', () => {
    expect(rejectionReason(fileOf('old.doc'))).toMatch(/Save as/i);
    expect(rejectionReason(fileOf('old.xls'))).toMatch(/Save as/i);
  });

  it('rejects files past the size cap, naming both sizes', () => {
    const big = new File([], 'big.pdf');
    Object.defineProperty(big, 'size', { value: 60 * 1024 * 1024 });
    expect(rejectionReason(big)).toBe('File is 60 MB — the limit is 50 MB.');
  });

  it('draws the line at exactly the cap, not one byte under it', () => {
    const sized = (size: number): File => {
      const file = new File([], 'edge.pdf');
      Object.defineProperty(file, 'size', { value: size });
      return file;
    };
    expect(rejectionReason(sized(MAX_FILE_BYTES))).toBeNull();
    expect(rejectionReason(sized(MAX_FILE_BYTES + 1))).not.toBeNull();
  });

  it('rejects empty files', () => {
    expect(rejectionReason(new File([], 'empty.csv'))).toBe('File is empty.');
  });
});

describe('formatBytes', () => {
  it('scales units', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5 MB');
    expect(formatBytes(2.35 * 1024 * 1024)).toBe('2.4 MB');
  });
});
