import { ConversionError, type Converter } from '../core/types';

/** PDF → layout-reconstructed Markdown via pdf.js. Built in phase 4. */
export const convert: Converter = async () => {
  throw new ConversionError('The PDF converter is not wired up yet (phase 4).');
};
