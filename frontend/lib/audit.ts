import { api, bearer, call, type Schema } from "@/lib/api";
import type { operations } from "@/lib/api/generated";

export type AuditEventRecord = Schema<"AuditEventRecord">;
export type AuditEventPage = Schema<"AuditEventPage">;
export type AuditOutcome = Schema<"AuditOutcome">;
export type AuditSource = Schema<"AuditSource">;
export type AuditExportFormat = Schema<"ExportFormat">;

/**
 * Every outcome the API accepts, in display order. Keyed by the generated `AuditOutcome`, so a
 * value added on the backend fails the type check until it is listed (and translated) here.
 */
export const AUDIT_OUTCOMES = Object.keys({
  success: true,
  failure: true,
  denied: true,
} satisfies Record<AuditOutcome, true>) as AuditOutcome[];

/** Every source the API accepts; keyed by the generated `AuditSource` like `AUDIT_OUTCOMES`. */
export const AUDIT_SOURCES = Object.keys({
  rest: true,
  mcp: true,
  chat: true,
  rag: true,
  cli: true,
  system: true,
} satisfies Record<AuditSource, true>) as AuditSource[];

type ListQuery = NonNullable<
  operations["list_events_api_v1_audit_events_get"]["parameters"]["query"]
>;

/** Filters the audit log can be narrowed by; an empty string means "not filtered". */
export type AuditFilters = Partial<
  Record<Exclude<keyof ListQuery, "limit" | "before_id" | "outcome" | "source">, string>
> & {
  outcome?: AuditOutcome | "";
  source?: AuditSource | "";
};

/** A downloaded export and the filename the server gave it. */
export interface AuditExport {
  blob: Blob;
  filename: string;
}

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
