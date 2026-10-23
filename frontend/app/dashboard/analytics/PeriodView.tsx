"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { RefreshCw } from "lucide-react";
import { useAuth } from "@/core/auth/hooks";
import { previousPeriod, type Bucket, type IsoDate } from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/core/components/ui/Button";
import { Forbidden } from "@/components/Forbidden";
import { Spinner } from "@/components/Spinner";
import { usePeriod } from "./usePeriod";

/** The selected period. */
export interface PeriodRange {
  from: IsoDate;
  to: IsoDate;
  bucket: Bucket;
}

/** The loaded rows of the selected period and the one before it. */
export type PeriodData<T> = { current: T[]; previous: T[] } & PeriodRange;

type Range = { from: IsoDate; to: IsoDate };

type State<D> =
  | { status: "loading" }
  | { status: "ready"; data: D; from: IsoDate; to: IsoDate }
  | { status: "forbidden" }
  | { status: "error" };

/** A `load` that fetches a read for the period and for the equal-length period before it. */
export function bothPeriods<T>(fetcher: (token: string, range: Range) => Promise<T[]>) {
  return (token: string, { from, to }: Range) =>
    Promise.all([fetcher(token, { from, to }), fetcher(token, previousPeriod(from, to))]).then(
      ([current, previous]) => ({ current, previous }),
    );
}

// API days are UTC calendar days; format them in UTC or a user west of UTC sees the day before.
const utc = (day: string) => new Date(`${day}T00:00:00Z`);

/**
 * An analytics page for the selected period: loads it with `load` (`bothPeriods` for a read
 * fetched once per period), shows loading, error (with retry) and access states, and renders
 * `children` with the loaded data and the period once it is ready.
 */
export function PeriodView<D>({
  title,
  subtitle,
  load,
  children,
}: {
  title: string;
  subtitle: (range: string) => string;
  load: (token: string, range: Range) => Promise<D>;
  children: (data: D & PeriodRange) => ReactNode;
}) {
  const { token } = useAuth();
  const t = useTranslations("analytics");
  const format = useFormatter();
  const { period } = usePeriod();
  const [state, setState] = useState<State<D>>({ status: "loading" });

  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    if (!token) return;
    let active = true;
    const { from, to } = period;
    setState({ status: "loading" });
    load(token, { from, to })
      .then((data) => {
        if (active) setState({ status: "ready", data, from, to });
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiRequestError && err.status === 403) {
          setState({ status: "forbidden" });
        } else {
          setState({ status: "error" });
        }
      });
    return () => {
      active = false;
    };
    // Only the bucket reshapes the loaded rows, so changing it doesn't refetch.
  }, [token, period.from, period.to, reloadKey]);

  const retry = useCallback(() => setReloadKey((key) => key + 1), []);

  // Access revoked after the layout's check: the read API answered 403.
  if (state.status === "forbidden") {
    return <Forbidden />;
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-foreground">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {subtitle(
            format.dateTimeRange(utc(period.from), utc(period.to), {
              dateStyle: "medium",
              timeZone: "UTC",
            }),
          )}
        </p>
      </div>

      {state.status === "loading" && (
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <Spinner className="mx-auto mb-4" />
            <p className="text-muted-foreground">{t("loading")}</p>
          </div>
        </div>
      )}

      {state.status === "error" && (
        <Alert severity="error">
          <div className="flex items-center justify-between gap-3">
            <span>{t("loadError")}</span>
            <Button variant="ghost" size="sm" onClick={retry}>
              <RefreshCw className="w-4 h-4 mr-1" aria-hidden="true" />
              {t("retry")}
            </Button>
          </div>
        </Alert>
      )}

      {state.status === "ready" &&
        children({
          ...state.data,
          from: state.from,
          to: state.to,
          bucket: period.bucket,
        })}
    </div>
  );
}

/** Labels and period-over-period changes shared by the analytics pages' cards and charts. */
export function useComparison({
  bucket,
  from,
  to,
  noPrevious,
}: {
  bucket: Bucket;
  from: IsoDate;
  to: IsoDate;
  noPrevious: string;
}) {
  const t = useTranslations("analytics.compare");
  const format = useFormatter();
  return {
    range: format.dateTimeRange(utc(from), utc(to), { dateStyle: "medium", timeZone: "UTC" }),
    // A bucket label is its first day: a week reads "Week of <Monday>", a month its month name.
    formatBucket(day: string) {
      if (bucket === "month") {
        return format.dateTime(utc(day), { month: "short", year: "numeric", timeZone: "UTC" });
      }
      const date = format.dateTime(utc(day), { dateStyle: "medium", timeZone: "UTC" });
      return bucket === "week" ? t("weekOf", { date }) : date;
    },
    // Zero before has no meaningful percentage, so say so rather than show Infinity%.
    change(cur: number, prev: number) {
      return prev === 0
        ? noPrevious
        : t("vsPrevious", {
            change: format.number(cur / prev - 1, {
              style: "percent",
              signDisplay: "exceptZero",
              maximumFractionDigits: 0,
            }),
          });
    },
  };
}
