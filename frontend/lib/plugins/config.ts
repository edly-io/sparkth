/**
 * Readers over a plugin's free-form config map.
 *
 * The backend stores plugin config as JSONB, so the generated schema types its
 * values as `unknown` — a value declared as a string in a config schema can
 * still arrive as an array, number, or null. These helpers narrow at the read
 * site so components never assert a value is a string without checking.
 */

import type { PluginConfig } from "./types";

/**
 * The value at `key` when it is a string, otherwise `undefined`.
 *
 * Non-string values are not coerced: a caller asking for a string field wants
 * to fall back to its default, not to receive `"[object Object]"`. The empty
 * string is returned as-is, since call sites read it as "set but empty".
 */
export function configString(config: PluginConfig | undefined, key: string): string | undefined {
  const value = config?.[key];
  return typeof value === "string" ? value : undefined;
}

/**
 * The whole config as text, for editors that render every field as an input.
 *
 * Strings pass through; anything else is JSON-encoded so that no field silently
 * disappears from the form. `null` and `undefined` become the empty string,
 * which the generic editor already treats as an unfilled field.
 */
export function stringConfigOf(config: PluginConfig | undefined): Record<string, string> {
  const entries = Object.entries(config ?? {}).map(([key, value]) => {
    if (typeof value === "string") return [key, value];
    if (value === null || value === undefined) return [key, ""];
    return [key, JSON.stringify(value)];
  });
  return Object.fromEntries(entries);
}
