import { ConversionError, type ConvertOptions, type ConversionResult, type SourceKind } from './types';

export const MAX_FILE_BYTES = 50 * 1024 * 1024;

const EXTENSION_KINDS: Record<string, SourceKind> = {
  pdf: 'pdf',
  docx: 'docx',
  xlsx: 'xlsx',
  xlsm: 'xlsx',
  csv: 'csv',
};

/** Formats we recognise well enough to explain why we cannot read them. */
const REJECTED_EXTENSIONS: Record<string, string> = {
  doc: 'Legacy .doc is not supported — open it in Word and "Save as" .docx.',
  xls: 'Legacy .xls is not supported — open it in Excel and "Save as" .xlsx.',
  ppt: 'PowerPoint files are not supported.',
  pptx: 'PowerPoint files are not supported.',
  pages: 'Apple Pages files are not supported — export to .docx or .pdf first.',
  numbers: 'Apple Numbers files are not supported — export to .xlsx or .csv first.',
  rtf: 'RTF is not supported — save as .docx first.',
  txt: 'Plain text needs no conversion.',
  md: 'That is already Markdown.',
};

export const ACCEPT_ATTRIBUTE = '.pdf,.docx,.xlsx,.xlsm,.csv';

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot === -1 ? '' : name.slice(dot + 1).toLowerCase();
}

export function kindFor(file: File): SourceKind | null {
  return EXTENSION_KINDS[extensionOf(file.name)] ?? null;
}

/**
 * Why a file cannot be queued, or null if it can. Kept separate from
 * `convert` so the UI can reject a batch member without spinning anything up.
 */
export function rejectionReason(file: File): string | null {
  const ext = extensionOf(file.name);
  if (!EXTENSION_KINDS[ext]) {
    return (
      REJECTED_EXTENSIONS[ext] ??
      `Unsupported file type${ext ? ` (.${ext})` : ''} — accepts ${ACCEPT_ATTRIBUTE}.`
    );
  }
  if (file.size > MAX_FILE_BYTES) {
    return `File is ${formatBytes(file.size)} — the limit is ${formatBytes(MAX_FILE_BYTES)}.`;
  }
  if (file.size === 0) return 'File is empty.';
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  // "50 MB" rather than "50.0 MB" — the decimal only earns its place when
  // there is something after it.
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(/\.0$/, '')} MB`;
}

/**
 * Loads the converter for `file`'s kind and runs it. Each converter — and the
 * heavy parsing library behind it — is a separate chunk pulled in on first
 * use, which is what keeps the initial bundle small.
 */
export async function convert(
  file: File,
  options: ConvertOptions,
): Promise<ConversionResult> {
  const kind = kindFor(file);
  if (!kind) throw new ConversionError(rejectionReason(file) ?? 'Unsupported file.');

  switch (kind) {
    case 'xlsx':
    case 'csv': {
      const { convert: run } = await import('../converters/spreadsheet');
      return run(file, options);
    }
    case 'docx': {
      const { convert: run } = await import('../converters/docx');
      return run(file, options);
    }
    case 'pdf': {
      const { convert: run } = await import('../converters/pdf');
      return run(file, options);
    }
  }
}
