"use client";

import { useCallback, useEffect, useState } from "react";
import { ChartColumn } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { fetchLoginActivity, type LoginActivityPoint } from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
import { BarChart, type BarChartDatum } from "@/components/ui/BarChart";
import { StatCard } from "@/components/ui/StatCard";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/Spinner";

const DAYS = 30;

// The API omits zero-login days (newest-first, sparse). Build a continuous
// oldest→newest series of `days` UTC days, filling missing days with 0. `now`
// is injectable so the derivation is unit-testable without faking the clock.
export function buildDailySeries(
  points: LoginActivityPoint[],
  days: number,
  now: Date,
): BarChartDatum[] {
  const counts = new Map(points.map((p) => [p.day, p.login_count]));
  const series: BarChartDatum[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setUTCDate(d.getUTCDate() - i);
    const key = d.toISOString().slice(0, 10); // YYYY-MM-DD (UTC), matches API `day`
    series.push({ label: key, value: counts.get(key) ?? 0 });
  }
  return series;
}

// Both stat tiles derive from the same windowed series the chart renders (not the raw API
// response), so they can never diverge from what's plotted. The read API's window floor is
// inclusive (`>= now - days`), so it can return a login dated exactly `today - days` — one day
// older than the chart's oldest slot (`today - (days - 1)`). Summarizing the raw response would
// let that boundary day inflate the stat tiles while having no bar in the chart.
export function summarize(series: BarChartDatum[]): {
  total: number;
  busiest: BarChartDatum | null;
} {
  const total = series.reduce((sum, d) => sum + d.value, 0);
  const busiest = series.reduce<BarChartDatum | null>(
    (best, d) => (!best || d.value > best.value ? d : best),
    null,
  );
  return { total, busiest };
}

type State =
  | { status: "loading" }
  | { status: "ready"; points: LoginActivityPoint[] }
  | { status: "forbidden" }
  | { status: "error"; message: string };

export default function AnalyticsPage() {
  const { token } = useAuth();
  const [state, setState] = useState<State>({ status: "loading" });

  const load = useCallback(async () => {
    if (!token) return;
    setState({ status: "loading" });
    try {
      const points = await fetchLoginActivity(token, { days: DAYS });
      setState({ status: "ready", points });
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 403) {
        setState({ status: "forbidden" });
      } else {
        setState({ status: "error", message: "We couldn't load analytics. Please try again." });
      }
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        <div className="mb-6 sm:mb-8 flex items-center gap-3">
          <ChartColumn className="w-6 h-6 text-primary-500" />
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Analytics</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Daily login activity over the last {DAYS} days.
            </p>
          </div>
        </div>

        {state.status === "loading" && (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <Spinner className="mx-auto mb-4" />
              <p className="text-muted-foreground">Loading analytics…</p>
            </div>
          </div>
        )}

        {state.status === "forbidden" && (
          <Alert severity="error">
            This page requires the <span className="font-mono">analytics.read</span> permission.
          </Alert>
        )}

        {state.status === "error" && <Alert severity="error">{state.message}</Alert>}

        {state.status === "ready" && state.points.length === 0 && (
          <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
            <ChartColumn className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
            <p className="text-muted-foreground">No logins in the last {DAYS} days.</p>
          </div>
        )}

        {state.status === "ready" && state.points.length > 0 && (
          <AnalyticsContent points={state.points} />
        )}
      </div>
    </div>
  );
}

function AnalyticsContent({ points }: { points: LoginActivityPoint[] }) {
  const series = buildDailySeries(points, DAYS, new Date());
  const { total, busiest } = summarize(series);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard title="Total logins" value={total} hint={`last ${DAYS} days`} />
        <StatCard title="Busiest day" value={busiest?.value ?? "—"} hint={busiest?.label} />
      </div>
      <div className="bg-card rounded-xl border border-border p-6">
        <BarChart data={series} />
      </div>
    </div>
  );
}
