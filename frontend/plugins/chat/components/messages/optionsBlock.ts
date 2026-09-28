const OPTIONS_FENCE = "```options";
const CLOSING_FENCE = "```";

export interface OptionsSplit {
  body: string;
  options: string[] | null;
}

/**
 * Split the trailing ```options fenced block off an assistant reply.
 *
 * The block counts only when nothing but whitespace follows it; an unclosed block counts too, so
 * a block still streaming in (or one the model left unclosed) is recognised. Options are the
 * block's trimmed, non-empty, de-duplicated lines. Any other content comes back unchanged with
 * `options: null`.
 */
export function splitOptionsBlock(content: string): OptionsSplit {
  const lines = content.split(/\r?\n/);
  const start = lines.findLastIndex((line) => line.trim() === OPTIONS_FENCE);
  if (start === -1) return { body: content, options: null };

  const rest = lines.slice(start + 1);
  const close = rest.findIndex((line) => line.trim() === CLOSING_FENCE);
  const blockLines = close === -1 ? rest : rest.slice(0, close);
  const trailing = close === -1 ? [] : rest.slice(close + 1);
  const options = [...new Set(blockLines.map((line) => line.trim()).filter(Boolean))];
  if (trailing.some((line) => line.trim() !== "") || options.length === 0) {
    return { body: content, options: null };
  }
  return { body: lines.slice(0, start).join("\n").trimEnd(), options };
}
