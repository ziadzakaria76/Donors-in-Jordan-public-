/** The document families Doc2MD knows how to read. */
export type SourceKind = 'pdf' | 'docx' | 'xlsx' | 'csv';

export interface ConvertOptions {
  /**
   * XLSX only: emit every row instead of truncating large sheets. Surfaced in
   * the UI as the "full export" toggle.
   */
  fullExport: boolean;
  /** Reports 0..1 progress plus an optional human-readable stage. */
  onProgress?: (fraction: number, stage?: string) => void;
  signal?: AbortSignal;
}

/**
 * Everything the front-matter builder and the UI need to describe a
 * conversion. Converters fill in what applies to their format and leave the
 * rest undefined.
 */
export interface ConversionMeta {
  pages?: number;
  sheets?: string[];
  /** Filenames of images that were replaced by placeholders. */
  images?: string[];
  /** Non-fatal problems worth showing the user (truncation, missing OCR...). */
  warnings: string[];
  /**
   * Output was cut short and re-running with `fullExport` would produce more.
   * Lets the UI act on its own truncation warning rather than only stating it.
   */
  truncated?: boolean;
}

export interface ConversionResult {
  /** Markdown body, before the shared post-processor runs over it. */
  markdown: string;
  meta: ConversionMeta;
}

/** Every converter module exports this under the name `convert`. */
export type Converter = (
  file: File,
  options: ConvertOptions,
) => Promise<ConversionResult>;

/** Raised for problems we can explain to the user rather than a stack trace. */
export class ConversionError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'ConversionError';
  }
}
