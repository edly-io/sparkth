"use client";

import { ListLoader } from "@/core/permissions/components/ui/ListLoader";

/** An entry the list shows: its name, and its description when it has one. */
export interface NamedEntry {
  id: number;
  name: string;
  description: string | null;
}

/**
 * Loads entries with the signed-in user's token and lists each one's name and description. Shows
 * a spinner while loading, `loadFailed` when loading fails and `empty` when there are none.
 */
export function NamedEntryList({
  label,
  load,
  empty,
  loadFailed,
}: {
  /** The list's accessible name. */
  label: string;
  load: (token: string) => Promise<NamedEntry[]>;
  empty: string;
  loadFailed: string;
}) {
  return (
    <ListLoader load={load} empty={empty} loadFailed={loadFailed}>
      {(entries) => (
        <ul
          aria-label={label}
          className="divide-y divide-border rounded-lg border border-border bg-card"
        >
          {entries.map(({ id, name, description }) => (
            <li key={id} className="px-4 py-3">
              <p className="font-medium text-foreground">{name}</p>
              {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
            </li>
          ))}
        </ul>
      )}
    </ListLoader>
  );
}
