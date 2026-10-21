"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  PERIOD_KEYS,
  createView,
  deleteView,
  exploreParams,
  fetchView,
  parseExploreConfig,
  updateView,
  type AnalyticsView,
  type ExploreConfig,
} from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/core/auth/hooks";
import { VIEWS_CHANGED } from "@/core/analytics/components/layout/AnalyticsNav";
import { useReplaceQuery } from "../usePeriod";

// Explore's URL keys that outlive a config change: the period and the open saved view.
const KEPT_KEYS = [...PERIOD_KEYS, "view"];

/** The URL query for `config` with `latest`'s period, and saved view `viewId` open when set. */
export function configQuery(
  latest: URLSearchParams,
  config: ExploreConfig,
  viewId: string | null,
): string {
  const kept = [...latest].filter(([k]) => PERIOD_KEYS.includes(k));
  return new URLSearchParams([
    ...kept,
    ...(viewId ? [["view", viewId]] : []),
    ...exploreParams(config),
  ]).toString();
}

/** The URL query showing saved `view`, keeping the period from `latest`. */
function viewQuery(latest: URLSearchParams, view: AnalyticsView): string {
  const saved: ExploreConfig = { ...parseExploreConfig(new URLSearchParams()), ...view.config };
  return configQuery(latest, saved, view.id);
}

/** What the last toolbar save or delete reported. */
export type ViewNotice = "saved" | "error" | null;

/** The saved view `?view=<id>` opens, and the actions on it. */
export interface SavedView {
  /** The open view, once loaded. */
  view: AnalyticsView | null;
  /** Why the open view didn't load: it doesn't exist for this viewer, or the request failed. */
  failure: "missing" | "error" | null;
  notice: ViewNotice;
  clearNotice: () => void;
  /** Saves `config` as a new view named `name` and opens it; rejects on failure. */
  saveNew: (name: string, config: ExploreConfig) => Promise<void>;
  /** Renames the open view; rejects on failure. */
  rename: (name: string) => Promise<void>;
  /** Replaces the open view's config with `config`, reporting the outcome as a notice. */
  save: (config: ExploreConfig) => Promise<void>;
  /** Deletes the open view and keeps `config` on screen, reporting a failure as a notice. */
  remove: (config: ExploreConfig) => Promise<void>;
}

/**
 * Loads the saved view the URL opens and, when the URL has no settings of its own, shows its
 * config. Saving or deleting tells the analytics rail to reload its list.
 */
export function useSavedView(): SavedView {
  const { token } = useAuth();
  const params = useSearchParams();
  const replaceQuery = useReplaceQuery();
  const viewId = params.get("view");
  const query = params.toString();
  // The last saved view fetched or written, by id; "missing" when it 404'd or 422'd, "error" otherwise.
  const [loaded, setLoaded] = useState<{
    id: string;
    view: AnalyticsView | "missing" | "error";
  } | null>(null);
  const [notice, setNotice] = useState<ViewNotice>(null);

  useEffect(() => {
    // A view this page just saved is already loaded.
    if (!token || !viewId || loaded?.id === viewId) return;
    let active = true;
    fetchView(token, viewId)
      .then((view) => {
        if (active) setLoaded({ id: viewId, view });
      })
      .catch((err: unknown) => {
        console.error("Saved analytics view failed to load:", err);
        if (active) {
          // 422: the id isn't a UUID, so no view can have it.
          const missing =
            err instanceof ApiRequestError && (err.status === 404 || err.status === 422);
          setLoaded({ id: viewId, view: missing ? "missing" : "error" });
        }
      });
    return () => {
      active = false;
    };
    // Fetched once per opened id.
  }, [token, viewId]);

  // A URL naming the open view but none of its settings (its rail link, or a first open) shows
  // the view's config, keeping the period; a URL with settings of its own keeps them.
  const shown = viewId && loaded?.id === viewId ? loaded.view : null;
  useEffect(() => {
    if (typeof shown !== "object" || !shown) return;
    replaceQuery((latest) =>
      [...latest.keys()].every((k) => KEPT_KEYS.includes(k))
        ? viewQuery(latest, shown)
        : latest.toString(),
    );
    // replaceQuery is stable.
  }, [shown, query]);

  const view = typeof shown === "object" ? shown : null;
  const open = (config: ExploreConfig, id: string | null) =>
    replaceQuery((latest) => configQuery(latest, config, id));
  const changed = (saved: AnalyticsView) => {
    setLoaded({ id: saved.id, view: saved });
    window.dispatchEvent(new Event(VIEWS_CHANGED));
  };
  // Toolbar actions report failure as a notice; the name dialog reports its own.
  const reportOutcome = async (action: () => Promise<void>, done: ViewNotice) => {
    try {
      await action();
      setNotice(done);
    } catch (err) {
      console.error("Saved analytics view action failed:", err);
      setNotice("error");
    }
  };

  return {
    view,
    failure: shown === "missing" || shown === "error" ? shown : null,
    notice,
    clearNotice: () => setNotice(null),
    saveNew: async (name, config) => {
      if (!token) return;
      const saved = await createView(token, name, config);
      changed(saved);
      open(config, saved.id);
    },
    rename: async (name) => {
      if (!token || !view) return;
      changed(await updateView(token, view.id, { name }));
    },
    save: (config) =>
      reportOutcome(async () => {
        if (token && view) changed(await updateView(token, view.id, { config }));
      }, "saved"),
    remove: (config) =>
      reportOutcome(async () => {
        if (!token || !view) return;
        await deleteView(token, view.id);
        window.dispatchEvent(new Event(VIEWS_CHANGED));
        open(config, null);
      }, null),
  };
}
