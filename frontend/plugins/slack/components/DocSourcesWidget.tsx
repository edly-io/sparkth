"use client";

/**
 * The settings control for a config field hinting the `doc-sources` widget.
 */

import type { ConfigWidgetProps } from "@/lib/settings/slots";
import DocSourcePicker from "./DocSourcePicker";

export default function DocSourcesWidget({ field, value, disabled, onChange }: ConfigWidgetProps) {
  const selected = Array.isArray(value)
    ? value.filter((s): s is string => typeof s === "string")
    : [];

  return (
    <div className="w-full">
      <DocSourcePicker
        label={field.label}
        value={selected}
        onChange={(next) => onChange(field.name, next)}
        disabled={disabled}
      />
      {field.description && (
        <p className="mt-1.5 text-sm text-muted-foreground">{field.description}</p>
      )}
    </div>
  );
}
