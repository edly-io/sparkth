import { api, bearer, call } from "@/lib/api";
import type { IsoDate } from "@/lib/analytics/dates";
import type { ExploreConfig } from "@/lib/analytics/explore";
import type { Bucket } from "@/lib/analytics/series";
import type {
  AnalyticsView,
  ComposeActivityPoint,
  DriveDocumentsPoint,
  EventCatalogEntry,
  ExploreResult,
  LoginsPoint,
  SummaryCount,
} from "@/lib/analytics/types";

/** Logins per day for the range; the page rolls days up itself, so a bucket change doesn't refetch. */
export async function fetchLogins(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<LoginsPoint[]> {
  return call<LoginsPoint[]>(() =>
    api.GET("/api/v1/analytics/logins", {
      params: { query: { from, to, bucket: "day" } },
      headers: bearer(token),
    }),
  );
}

export async function fetchComposeActivity(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<ComposeActivityPoint[]> {
  return call<ComposeActivityPoint[]>(() =>
    api.GET("/api/v1/compose/analytics/activity", {
      params: { query: { from, to, bucket: "day" } },
      headers: bearer(token),
    }),
  );
}

/** Processed Drive documents per day and outcome, with summed seconds to final, for the period. */
export async function fetchDriveDocuments(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<DriveDocumentsPoint[]> {
  return call<DriveDocumentsPoint[]>(() =>
    api.GET("/api/v1/google-drive/analytics/documents", {
      params: { query: { from, to, bucket: "day" } },
      headers: bearer(token),
    }),
  );
}

/** Every Overview figure, counted for the period and the one before it, in one request. */
export async function fetchSummary(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<SummaryCount[]> {
  return call<SummaryCount[]>(() =>
    api.GET("/api/v1/analytics/summary", {
      params: { query: { from, to } },
      headers: bearer(token),
    }),
  );
}

/** Every recorded event type and its payload fields, for Explore's pickers. */
export async function fetchEventCatalog(token: string): Promise<EventCatalogEntry[]> {
  return call<EventCatalogEntry[]>(() =>
    api.GET("/api/v1/analytics/events", { headers: bearer(token) }),
  );
}

/** An Explore config's measure per bucket and group for the period; unset parts are not sent. */
export async function fetchExplore(
  token: string,
  { from, to, bucket }: { from: IsoDate; to: IsoDate; bucket: Bucket },
  config: ExploreConfig,
): Promise<ExploreResult> {
  return call<ExploreResult>(() =>
    api.GET("/api/v1/analytics/query", {
      params: {
        query: {
          from,
          to,
          bucket,
          event_type: config.event ?? "",
          measure: config.measure,
          actor_id: config.actor ?? undefined,
          filter: config.filters.map((f) => `${f.field}:${f.value}`),
          group_by: config.groupBy ?? undefined,
        },
      },
      headers: bearer(token),
    }),
  );
}

/** The caller's saved Explore views, by name. */
export async function listViews(token: string): Promise<AnalyticsView[]> {
  return call<AnalyticsView[]>(() =>
    api.GET("/api/v1/analytics/views", { headers: bearer(token) }),
  );
}

/** One of the caller's saved views; rejects with status 404 when it's missing or not theirs. */
export async function fetchView(token: string, id: string): Promise<AnalyticsView> {
  return call<AnalyticsView>(() =>
    api.GET("/api/v1/analytics/views/{view_id}", {
      params: { path: { view_id: id } },
      headers: bearer(token),
    }),
  );
}

/** Saves a config as a new view; rejects with status 409 when the name is taken. */
export async function createView(
  token: string,
  name: string,
  config: ExploreConfig,
): Promise<AnalyticsView> {
  return call<AnalyticsView>(() =>
    api.POST("/api/v1/analytics/views", { body: { name, config }, headers: bearer(token) }),
  );
}

/** Renames a view and/or replaces its config. */
export async function updateView(
  token: string,
  id: string,
  change: { name?: string; config?: ExploreConfig },
): Promise<AnalyticsView> {
  return call<AnalyticsView>(() =>
    api.PATCH("/api/v1/analytics/views/{view_id}", {
      params: { path: { view_id: id } },
      body: change,
      headers: bearer(token),
    }),
  );
}

/** Deletes a view. */
export async function deleteView(token: string, id: string): Promise<void> {
  await call(() =>
    api.DELETE("/api/v1/analytics/views/{view_id}", {
      params: { path: { view_id: id } },
      headers: bearer(token),
    }),
  );
}
