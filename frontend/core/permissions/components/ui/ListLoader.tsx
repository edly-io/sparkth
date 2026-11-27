"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/core/auth/hooks";
import { Alert } from "@/core/components/ui/Alert";
import { Spinner } from "@/core/components/ui/Spinner";

type LoadState<T> =
  | { status: "loading" }
  | { status: "failed" }
  | { status: "loaded"; entries: T[] };

/**
 * Loads entries with the signed-in user's token and hands them to `children` to show, and to
 * `onLoaded` for use elsewhere on the page. Shows a spinner while loading, `loadFailed` when loading
 * fails and `empty` when there are none. Loads again when the token or `reloadKey` changes, and goes
 * back to loading when the token goes away.
 */
export function ListLoader<T>({
  load,
  empty,
  loadFailed,
  reloadKey,
  onLoaded,
  children,
}: {
  load: (token: string) => Promise<T[]>;
  empty: string;
  loadFailed: string;
  /** Changing it loads the entries again, after the caller has changed them. */
  reloadKey?: number;
  /** Called with the entries each time they load. Pass a stable function, such as a state setter. */
  onLoaded?: (entries: T[]) => void;
  children: (entries: T[]) => ReactNode;
}) {
  const { token } = useAuth();
  const [state, setState] = useState<LoadState<T>>({ status: "loading" });

  useEffect(() => {
    setState({ status: "loading" });
    if (!token) return;
    let active = true;
    load(token)
      .then((entries) => {
        if (!active) return;
        setState({ status: "loaded", entries });
        onLoaded?.(entries);
      })
      .catch((error: unknown) => {
        console.error("Loading the list failed:", error);
        if (active) setState({ status: "failed" });
      });
    return () => {
      active = false;
    };
  }, [token, load, reloadKey, onLoaded]);

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
  return children(state.entries);
}
