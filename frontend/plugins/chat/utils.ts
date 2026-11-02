/** The longest attachment or source name chat shows before truncating it. */
export const RAG_DISPLAY_NAME_MAX_CHARS = parseInt(
  process.env.NEXT_PUBLIC_RAG_DISPLAY_NAME_MAX_CHARS ?? "30",
  10,
);

/** Cuts `text` to at most `maxChars` characters, ending in an ellipsis when it was cut. */
export function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars - 1) + "…";
}
