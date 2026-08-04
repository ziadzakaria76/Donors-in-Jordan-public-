import { ConversionError, type Converter } from '../core/types';

/** XLSX / XLSM / CSV → GFM tables. Built in phase 2. */
export const convert: Converter = async () => {
  throw new ConversionError('The spreadsheet converter is not wired up yet (phase 2).');
};
