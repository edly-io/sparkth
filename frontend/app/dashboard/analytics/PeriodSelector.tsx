"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import {
  BUCKETS,
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

export function PeriodSelector() {
  const t = useTranslations("analytics.period");
  const { period, error: urlError, setPeriod } = usePeriod();
  const today = toIsoDate(new Date());
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
    setPeriod(presetPeriod(value as Preset, period.bucket, today));
  }

  function applyCustom(event: FormEvent) {
    event.preventDefault();
    const rangeError = validateRange(draft.from, draft.to, today);
    setDraftError(rangeError);
    if (rangeError === null) setPeriod({ ...draft, bucket: period.bucket, preset: null });
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
          onChange={(e) => setPeriod({ ...period, bucket: e.target.value as Bucket })}
          options={BUCKETS.map((b) => ({ value: b, label: t(`buckets.${b}`) }))}
        />
      </div>
      {error && (
        <p id="period-error" role="alert" className="w-full text-sm text-error-600">
          {t(`errors.${error}`)}
        </p>
      )}
    </div>
  );
}
