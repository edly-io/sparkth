"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import {
  addDays,
  BUCKETS,
  MAX_RANGE_DAYS,
  PRESETS,
  presetPeriod,
  toIsoDate,
  validateRange,
  type Bucket,
  type Preset,
  type RangeError,
} from "@/lib/analytics";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { usePeriod } from "./usePeriod";

const PRESET_KEYS = Object.keys(PRESETS) as Preset[];

// Remounts (reseeding the custom toggle, draft and inline error) when the range in the URL
// changes, but not for a bucket change, so an unapplied custom draft survives it.
export function PeriodSelector() {
  const { period } = usePeriod();
  return <PeriodControls key={period.preset ?? `${period.from}|${period.to}`} />;
}

function PeriodControls() {
  const t = useTranslations("analytics.period");
  const { period, error: urlError, setPeriod } = usePeriod();
  const today = toIsoDate(new Date());
  // The read API counts back from today, so a start older than this can't be served.
  const earliestStart = addDays(today, -(MAX_RANGE_DAYS - 1));
  const [custom, setCustom] = useState(period.preset === null);
  const [draft, setDraft] = useState({ from: period.from, to: period.to });
  const [draftError, setDraftError] = useState<RangeError | null>(null);
  const error = draftError ?? urlError;

  function onRange(value: string) {
    if (value === "custom") {
      setCustom(true);
      setDraft({ from: period.from, to: period.to });
      return;
    }
    setCustom(false);
    setDraftError(null);
    setPeriod((current) => presetPeriod(value as Preset, current.bucket, today));
  }

  function applyCustom(event: FormEvent) {
    event.preventDefault();
    const rangeError = validateRange(draft.from, draft.to, today);
    setDraftError(rangeError);
    if (rangeError === null) {
      setPeriod((current) => ({ ...draft, bucket: current.bucket, preset: null }));
    }
  }

  const describedBy = error ? "period-error" : undefined;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="w-44">
        <Select
          id="period-range"
          label={t("range")}
          value={custom ? "custom" : (period.preset ?? "custom")}
          onChange={(e) => onRange(e.target.value)}
          options={[
            ...PRESET_KEYS.map((p) => ({ value: p, label: t(`presets.${p}`) })),
            { value: "custom", label: t("presets.custom") },
          ]}
        />
      </div>
      {custom && (
        <form noValidate onSubmit={applyCustom} className="flex flex-wrap items-end gap-3">
          <div className="w-44">
            <Input
              type="date"
              id="period-from"
              label={t("from")}
              value={draft.from}
              min={earliestStart}
              max={today}
              aria-invalid={error !== null}
              aria-describedby={describedBy}
              onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value }))}
            />
          </div>
          <div className="w-44">
            <Input
              type="date"
              id="period-to"
              label={t("to")}
              value={draft.to}
              min={earliestStart}
              max={today}
              aria-invalid={error !== null}
              aria-describedby={describedBy}
              onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value }))}
            />
          </div>
          <Button type="submit" variant="outline">
            {t("apply")}
          </Button>
        </form>
      )}
      <div className="w-36">
        <Select
          id="period-bucket"
          label={t("bucket")}
          value={period.bucket}
          onChange={(e) => {
            const bucket = e.target.value as Bucket;
            setPeriod((current) => ({ ...current, bucket }));
          }}
          options={BUCKETS.map((b) => ({ value: b, label: t(`buckets.${b}`) }))}
        />
      </div>
      {error && (
        <p id="period-error" role="alert" className="w-full text-sm text-error-600">
          {t(`errors.${error}`, { days: MAX_RANGE_DAYS })}
        </p>
      )}
    </div>
  );
}
