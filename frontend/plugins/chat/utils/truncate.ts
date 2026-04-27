/**
 * Truncates a string to `max` characters, appending an ellipsis if needed.
 * Uses the Unicode ellipsis character (…) for single-char width.
 */
export function truncate(text: string, max: number = 25): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "…";
}
