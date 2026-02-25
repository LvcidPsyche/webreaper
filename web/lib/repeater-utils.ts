export function headersToText(headers: Record<string, string> | string | null | undefined): string {
  if (!headers) return '';
  if (typeof headers === 'string') return headers;
  return Object.entries(headers).map(([k, v]) => `${k}: ${v}`).join('\n');
}

export function headersFromText(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const i = trimmed.indexOf(':');
    if (i <= 0) continue;
    out[trimmed.slice(0, i).trim()] = trimmed.slice(i + 1).trim();
  }
  return out;
}

export function decoderOutputToText(output: unknown): string {
  if (output == null) return '';
  return typeof output === 'string' ? output : JSON.stringify(output, null, 2);
}
