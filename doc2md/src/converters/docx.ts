import { ConversionError, type Converter } from '../core/types';

/** DOCX → semantic HTML (mammoth) → Markdown (turndown). Built in phase 3. */
export const convert: Converter = async () => {
  throw new ConversionError('The DOCX converter is not wired up yet (phase 3).');
};
