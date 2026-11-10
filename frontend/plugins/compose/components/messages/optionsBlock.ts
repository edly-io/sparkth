const OPTIONS_FENCE = "```options";
const SINGLE_OPTIONS_FENCE = "```options single";
const CLOSING_FENCE = "```";

export interface OptionsSplit {
  body: string;
  options: string[] | null;
  closed: boolean;
  single: boolean;
}

/**
 * Split the trailing ```options fenced block off an assistant reply.
 *
 * The block counts only when nothing but whitespace follows it; an unclosed block counts too, so
 * a block still streaming in (or one the model left unclosed) is recognised, with `closed: false`.
 * Options are the block's trimmed, non-empty, de-duplicated lines. A ```options single fence marks
 * a question with exactly one answer (`single: true`); a plain ```options fence allows several.
 * Any other content comes back unchanged with `options: null`.
 */
export function splitOptionsBlock(content: string): OptionsSplit {
  const lines = content.split(/\r?\n/);
  const start = lines.findLastIndex((line) =>
    [OPTIONS_FENCE, SINGLE_OPTIONS_FENCE].includes(line.trim()),
  );
  if (start === -1) return { body: content, options: null, closed: false, single: false };
  const single = lines[start].trim() === SINGLE_OPTIONS_FENCE;

  const rest = lines.slice(start + 1);
  const close = rest.findIndex((line) => line.trim() === CLOSING_FENCE);
  const blockLines = close === -1 ? rest : rest.slice(0, close);
  const trailing = close === -1 ? [] : rest.slice(close + 1);
  const options = [...new Set(blockLines.map((line) => line.trim()).filter(Boolean))];
  if (trailing.some((line) => line.trim() !== "") || options.length === 0) {
    return { body: content, options: null, closed: false, single: false };
  }
  return {
    body: lines.slice(0, start).join("\n").trimEnd(),
    options,
    closed: close !== -1,
    single,
  };
}

/** The options that appear as whole lines of the author's `reply`, in display order. */
export function answeredOptions(options: string[], reply: string): string[] {
  const lines = reply.split(/\r?\n/).map((line) => line.trim());
  return options.filter((option) => lines.includes(option));
}

/**
 * `message` with `line` added on a new line, or unchanged when a trimmed line of it already
 * equals `line`. A blank message becomes just `line`.
 */
export function appendLine(message: string, line: string): string {
  if (message.split(/\r?\n/).some((existing) => existing.trim() === line)) return message;
  const kept = message.trimEnd();
  return kept ? `${kept}\n${line}` : line;
}

/** `message` without the lines equal to `remove`, then `add` appended as by `appendLine`. */
export function replaceLine(message: string, remove: string, add: string): string {
  const kept = message.split(/\r?\n/).filter((line) => line.trim() !== remove);
  return appendLine(kept.join("\n"), add);
}
