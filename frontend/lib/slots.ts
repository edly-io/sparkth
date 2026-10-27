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

/** A slot whose readers look one item up by its `name`, such as an icon. */
export type NamedSlot<T extends { name: string }> = Slot<T>;

/** Set `plugin`'s items in `slot`. Throws when another plugin already set an item of one of their names. */
export function setNamedSlotItems<T extends { name: string }>(
  slot: NamedSlot<T>,
  plugin: string,
  items: T[],
): void {
  const names = new Set(items.map((item) => item.name));
  const clash = slotItems(slot).find(([owner, item]) => owner !== plugin && names.has(item.name));
  if (clash) throw new Error(`The slot item "${clash[1].name}" is already set by "${clash[0]}"`);
  slot.set(plugin, items);
}

/**
 * The item named `name` in `slot`, whichever plugin set it and whether or not that plugin is enabled.
 * The reader decides which plugins to show before it looks an item up.
 */
export function namedSlotItem<T extends { name: string }>(
  slot: NamedSlot<T>,
  name: string,
): T | undefined {
  return slotItems(slot).find(([, item]) => item.name === name)?.[1];
}
