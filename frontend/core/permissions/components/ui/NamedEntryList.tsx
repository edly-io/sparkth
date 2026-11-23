"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/core/auth/hooks";
import { Alert } from "@/core/components/ui/Alert";
import { Spinner } from "@/core/components/ui/Spinner";

/** An entry the list shows: its name, and its description when it has one. */
export interface NamedEntry {
  id: number;
  name: string;
  description: string | null;
}

type ListState =
  | { status: "loading" }
  | { status: "failed" }
  | { status: "loaded"; entries: NamedEntry[] };

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
  const { token } = useAuth();
  const [state, setState] = useState<ListState>({ status: "loading" });

  useEffect(() => {
    setState({ status: "loading" });
    if (!token) return;
    let active = true;
    load(token)
      .then((entries) => {
        if (active) setState({ status: "loaded", entries });
      })
      .catch((error: unknown) => {
        console.error("Loading the list failed:", error);
        if (active) setState({ status: "failed" });
      });
    return () => {
      active = false;
    };
  }, [token, load]);

  if (state.status === "loading") {
    return (
      <div className="flex justify-center py-24">
        <Spinner />
      </div>
    );
  }
  if (state.status === "failed") return <Alert severity="error">{loadFailed}</Alert>;
  if (state.entries.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border p-12 text-center text-muted-foreground">
        {empty}
      </div>
    );
  }
  return (
    <ul
      aria-label={label}
      className="divide-y divide-border rounded-lg border border-border bg-card"
    >
      {state.entries.map(({ id, name, description }) => (
        <li key={id} className="px-4 py-3">
          <p className="font-medium text-foreground">{name}</p>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </li>
      ))}
    </ul>
  );
}
