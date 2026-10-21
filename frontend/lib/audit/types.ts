import type { Schema } from "@/lib/api";
import type { operations } from "@/lib/api/generated";

export type AuditEventSummary = Schema<"AuditEventSummary">;
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

/** The query parameters the audit listing accepts, as generated from the backend schema. */
export type ListQuery = NonNullable<
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
