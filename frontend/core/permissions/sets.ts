/** A copy of `set` without `item` when it has it, with `item` added when it doesn't. */
export function toggleItem<T>(set: ReadonlySet<T>, item: T): Set<T> {
  const next = new Set(set);
  if (!next.delete(item)) next.add(item);
  return next;
}
