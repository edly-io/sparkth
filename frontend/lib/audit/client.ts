import { api, bearer, call } from "@/lib/api";
import type {
  AuditEventPage,
  AuditEventRecord,
  AuditExport,
  AuditExportFormat,
  AuditFilters,
  ListQuery,
} from "@/lib/audit/types";

function activeFilters(filters: AuditFilters): ListQuery {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ""),
  ) as ListQuery;
}

function attachmentFilename(response: Response): string | null {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  return /filename="([^"]+)"/.exec(disposition)?.[1] ?? null;
}

/** One page of audit event summaries, most recently recorded first; pass `next_before_id` back as `beforeId` for the next. */
export async function fetchAuditEvents(
  token: string,
  filters: AuditFilters,
  beforeId?: number,
): Promise<AuditEventPage> {
  return call<AuditEventPage>(() =>
    api.GET("/api/v1/audit/events", {
      params: { query: { ...activeFilters(filters), before_id: beforeId } },
      headers: bearer(token),
    }),
  );
}

/** One audit event in full (request metadata, changed values, tool and model details). */
export async function fetchAuditEvent(token: string, eventId: number): Promise<AuditEventRecord> {
  return call<AuditEventRecord>(() =>
    api.GET("/api/v1/audit/events/{event_id}", {
      params: { path: { event_id: eventId } },
      headers: bearer(token),
    }),
  );
}

/** Every category an audit event can carry, sorted, for the category filter. */
export async function fetchAuditCategories(token: string): Promise<string[]> {
  return call<string[]>(() =>
    api.GET("/api/v1/audit/categories", {
      headers: bearer(token),
    }),
  );
}

/**
 * Every event matching `filters` as a CSV or JSON Lines file, named as the server's
 * `Content-Disposition` says (timestamped). The backend records the export.
 */
export async function exportAuditEvents(
  token: string,
  filters: AuditFilters,
  format: AuditExportFormat,
): Promise<AuditExport> {
  let filename = `audit-events.${format}`;
  const blob = await call<Blob>(async () => {
    const result = await api.GET("/api/v1/audit/events/export", {
      params: { query: { ...activeFilters(filters), format } },
      parseAs: "blob",
      headers: bearer(token),
    });
    filename = attachmentFilename(result.response) ?? filename;
    return result;
  });
  return { blob, filename };
}
