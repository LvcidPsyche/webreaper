import { describe, expect, it } from 'vitest';
import { headersFromText, headersToText, decoderOutputToText } from '../repeater-utils';

describe('repeater-utils', () => {
  it('round-trips header editor text state', () => {
    const headers = { 'Content-Type': 'application/json', Accept: '*/*' };
    const text = headersToText(headers);
    const parsed = headersFromText(text);
    expect(parsed['Content-Type']).toBe('application/json');
    expect(parsed['Accept']).toBe('*/*');
  });

  it('ignores malformed header lines', () => {
    const parsed = headersFromText('BadLine\nX-Test: 1');
    expect(parsed).toEqual({ 'X-Test': '1' });
  });

  it('formats decoder transform output', () => {
    expect(decoderOutputToText('plain')).toBe('plain');
    expect(decoderOutputToText({ a: 1 })).toContain('"a": 1');
  });
});
