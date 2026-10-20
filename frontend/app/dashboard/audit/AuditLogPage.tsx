"use client";

import { Fragment, useCallback, useEffect, useRef, useState, type SubmitEvent } from "react";
import { ChevronDown, ChevronRight, Download, ScrollText } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useAuth } from "@/lib/auth-context";
import { usePermission } from "@/lib/permissions";
import { ApiRequestError } from "@/lib/api";
import {
  AUDIT_OUTCOMES,
  AUDIT_SOURCES,
  exportAuditEvents,
  fetchAuditCategories,
  fetchAuditEvents,
  type AuditEventRecord,
  type AuditExportFormat,
  type AuditFilters,
  type AuditOutcome,
} from "@/lib/audit";
import { downloadBlob } from "@/lib/download";
import { Forbidden } from "@/components/Forbidden";
import { Spinner } from "@/components/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

interface FilterForm {
  from: string;
  to: string;
  actor_id: string;
  category: string;
  outcome: string;
  source: string;
}

const EMPTY_FORM: FilterForm = {
  from: "",
  to: "",
  actor_id: "",
  category: "",
  outcome: "",
  source: "",
};

// datetime-local inputs carry the viewer's local time, to the minute; the API wants an aware ISO
// timestamp, and "to" covers the whole of its minute.
function toFilters(form: FilterForm): AuditFilters {
  const filters: AuditFilters = {};
  if (form.from) filters.from = new Date(form.from).toISOString();
  if (form.to) filters.to = new Date(new Date(form.to).getTime() + 59_999).toISOString();
  if (form.actor_id.trim()) filters.actor_id = form.actor_id.trim();
  if (form.category) filters.category = form.category;
  if (form.outcome) filters.outcome = form.outcome as AuditFilters["outcome"];
  if (form.source) filters.source = form.source as AuditFilters["source"];
  return filters;
}

function details(event: AuditEventRecord): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(event).filter(([key, value]) => value !== null && key !== "id"),
  );
}

/** Administrators' view of the audit trail: filter, page through and export recorded events. */
export default function AuditLogPage() {
  const { token } = useAuth();
  const t = useTranslations("audit");
  const format = useFormatter();
  const access = usePermission(token, "audit.read");
  const [form, setForm] = useState<FilterForm>(EMPTY_FORM);
  const [categories, setCategories] = useState<string[]>([]);
  const [filters, setFilters] = useState<AuditFilters>({});
  const [events, setEvents] = useState<AuditEventRecord[]>([]);
  const [nextBeforeId, setNextBeforeId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<AuditExportFormat | null>(null);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const latestRequest = useRef(0);

  useEffect(() => {
    if (access !== "allowed" || !token) return;
    fetchAuditCategories(token)
      .then(setCategories)
      .catch((err: unknown) => console.error("Audit categories failed to load:", err));
  }, [access, token]);

  const load = useCallback(
    async (beforeId?: number) => {
      if (!token) return;
      // Only the newest request may touch the list, so a page fetched for older filters
      // can't land on top of the current ones.
      const request = ++latestRequest.current;
      setLoading(true);
      setError("");
      try {
        const page = await fetchAuditEvents(token, filters, beforeId);
        if (request !== latestRequest.current) return;
        setEvents((current) => (beforeId === undefined ? page.items : [...current, ...page.items]));
        setNextBeforeId(page.next_before_id ?? null);
      } catch (err) {
        if (request !== latestRequest.current) return;
        setError(err instanceof ApiRequestError ? err.message : t("loadError"));
      } finally {
        if (request === latestRequest.current) setLoading(false);
      }
    },
    [token, filters, t],
  );

  useEffect(() => {
    if (access === "allowed") load();
  }, [access, load]);

  const handleApply = (e: SubmitEvent) => {
    e.preventDefault();
    setExpanded(null);
    setFilters(toFilters(form));
  };

  const handleExport = async (exportFormat: AuditExportFormat) => {
    if (!token) return;
    setExporting(exportFormat);
    setError("");
    try {
      const { blob, filename } = await exportAuditEvents(token, filters, exportFormat);
      downloadBlob(blob, filename);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : t("exportError"));
    } finally {
      setExporting(null);
    }
  };

  const field = (name: keyof FilterForm) => ({
    name,
    value: form[name],
    onChange: (e: { target: { value: string } }) =>
      setForm((current) => ({ ...current, [name]: e.target.value })),
  });

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center gap-3">
          <ScrollText className="w-6 h-6 text-primary-500" aria-hidden="true" />
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{t("title")}</h1>
        </div>

        {access === "checking" && (
          <div className="flex justify-center py-24">
            <Spinner />
          </div>
        )}
        {access === "denied" && <Forbidden />}
        {access === "allowed" && (
          <>
            <p className="mb-6 text-sm text-muted-foreground">{t("subtitle")}</p>

            <form
              onSubmit={handleApply}
              className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 items-end"
            >
              <Input id="audit-from" type="datetime-local" label={t("from")} {...field("from")} />
              <Input id="audit-to" type="datetime-local" label={t("to")} {...field("to")} />
              <Input
                id="audit-actor"
                label={t("actorId")}
                placeholder={t("actorIdPlaceholder")}
                {...field("actor_id")}
              />
              <Select
                id="audit-category"
                label={t("category")}
                options={[
                  { value: "", label: t("any") },
                  ...categories.map((value) => ({ value, label: value })),
                ]}
                {...field("category")}
              />
              <Select
                id="audit-outcome"
                label={t("outcome")}
                options={[
                  { value: "", label: t("any") },
                  ...AUDIT_OUTCOMES.map((value) => ({
                    value,
                    label: t(`outcomes.${value}`),
                  })),
                ]}
                {...field("outcome")}
              />
              <Select
                id="audit-source"
                label={t("source")}
                options={[
                  { value: "", label: t("any") },
                  ...AUDIT_SOURCES.map((value) => ({ value, label: value })),
                ]}
                {...field("source")}
              />
              <div className="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-3 xl:col-span-6">
                <Button type="submit">{t("apply")}</Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setForm(EMPTY_FORM);
                    setFilters({});
                  }}
                >
                  {t("reset")}
                </Button>
                <div className="flex gap-2 sm:ml-auto">
                  {(["csv", "jsonl"] as const).map((exportFormat) => (
                    <Button
                      key={exportFormat}
                      type="button"
                      variant="outline"
                      loading={exporting === exportFormat}
                      disabled={exporting !== null}
                      spinnerLabel={t("exporting")}
                      onClick={() => handleExport(exportFormat)}
                    >
                      <Download className="w-4 h-4 mr-1" aria-hidden="true" />
                      {t(exportFormat === "csv" ? "exportCsv" : "exportJsonl")}
                    </Button>
                  ))}
                </div>
              </div>
            </form>

            {error && (
              <Alert severity="error" className="mb-4">
                {error}
              </Alert>
            )}

            {events.length > 0 ? (
              <div className="bg-card rounded-lg shadow-sm overflow-x-auto border border-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-surface-variant/50 text-left text-muted-foreground">
                      <th className="w-10 px-2 py-3" />
                      <th className="px-4 py-3 font-medium">{t("columns.time")}</th>
                      <th className="px-4 py-3 font-medium">{t("columns.event")}</th>
                      <th className="px-4 py-3 font-medium">{t("columns.actor")}</th>
                      <th className="px-4 py-3 font-medium">{t("columns.outcome")}</th>
                      <th className="px-4 py-3 font-medium hidden md:table-cell">
                        {t("columns.target")}
                      </th>
                      <th className="px-4 py-3 font-medium hidden md:table-cell">
                        {t("columns.source")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <Fragment key={event.id}>
                        <tr className="border-b border-border last:border-b-0 align-top">
                          <td className="px-2 py-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-expanded={expanded === event.id}
                              aria-label={
                                expanded === event.id ? t("hideDetails") : t("showDetails")
                              }
                              onClick={() => setExpanded(expanded === event.id ? null : event.id)}
                            >
                              {expanded === event.id ? (
                                <ChevronDown className="w-4 h-4" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                            </Button>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                            {format.dateTime(new Date(event.occurred_at), {
                              dateStyle: "medium",
                              timeStyle: "medium",
                            })}
                          </td>
                          <td className="px-4 py-3 font-mono text-foreground">
                            {`${event.category}.${event.action}`}
                          </td>
                          <td className="px-4 py-3 text-foreground">
                            {event.actor_label ?? event.actor_id ?? event.actor_type}
                          </td>
                          <td className="px-4 py-3">
                            {t(`outcomes.${event.outcome as AuditOutcome}`)}
                          </td>
                          <td className="px-4 py-3 font-mono text-muted-foreground hidden md:table-cell">
                            {event.target_type
                              ? `${event.target_type}${event.target_id ? `:${event.target_id}` : ""}`
                              : ""}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                            {event.source}
                          </td>
                        </tr>
                        {expanded === event.id && (
                          <tr className="border-b border-border bg-surface-variant/30">
                            <td colSpan={7} className="px-4 py-3">
                              <pre className="overflow-x-auto whitespace-pre-wrap break-all text-xs text-foreground">
                                {JSON.stringify(details(event), null, 2)}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              !loading && (
                <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
                  <ScrollText className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                  <p className="text-muted-foreground">{t("empty")}</p>
                </div>
              )
            )}

            {loading && (
              <div className="flex justify-center py-6">
                <Spinner />
              </div>
            )}
            {!loading && nextBeforeId !== null && (
              <div className="mt-4 flex justify-center">
                <Button variant="outline" onClick={() => load(nextBeforeId)}>
                  {t("loadMore")}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
