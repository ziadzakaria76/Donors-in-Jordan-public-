import type { ConversionMeta } from './types';

/**
 * Rough token estimate. Four characters per token is the usual back-of-envelope
 * figure for English prose and is close enough to be useful as a live counter.
 */
export function estimateTokens(markdown: string): number {
  return Math.ceil(markdown.length / 4);
}

export function countWords(markdown: string): number {
  const words = markdown.trim().match(/\S+/g);
  return words ? words.length : 0;
}

export interface FinalizeInput {
  filename: string;
  markdown: string;
  meta: ConversionMeta;
}

/**
 * Applies the shared token-efficiency pass and prepends YAML front-matter.
 * Phase 1 ships the identity transform so the pipeline is whole; the real
 * normalisation lands in phase 5.
 */
export function finalize(input: FinalizeInput): string {
  return input.markdown;
}
