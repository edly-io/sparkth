import { api, bearer, call } from "@/lib/api";
import type {
  AuditEventPage,
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

/** One page of audit events, newest first; pass `next_before_id` back as `beforeId` for the next. */
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
