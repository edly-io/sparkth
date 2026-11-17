/** The longest document name (an attachment or a source) Compose shows before truncating it. */
export const DOCUMENT_DISPLAY_NAME_MAX_CHARS = 30;

/** Cuts `text` to at most `maxChars` characters, ending in an ellipsis when it was cut. */
export function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars - 1) + "…";
}
