/**
 * Slots: how plugins contribute to core screens and to each other.
 */

/**
 * Each plugin name mapped to the items that plugin set. Declare one as `new Map()`; a plugin sets
 * its items with `slot.set(plugin, items)`.
 */
export type Slot<T> = Map<string, T[]>;

/** Every item in `slot` with the plugin that set it, ordered by plugin name. */
export function slotItems<T>(slot: Slot<T>): [plugin: string, item: T][] {
  const plugins = [...slot.keys()].sort();
  return plugins.flatMap((plugin) =>
    (slot.get(plugin) ?? []).map((item): [string, T] => [plugin, item]),
  );
}
