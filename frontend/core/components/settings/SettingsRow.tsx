"use client";

import { useState, type ReactNode } from "react";
import { Switch } from "@/components/ui/Switch";

// The row's on/off status, coloured by whether it's on.
function StatusBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
        active
          ? "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300"
          : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400"
      }`}
    >
      {label}
    </span>
  );
}

/**
 * One settings row: what it is, its status, its actions and a labelled on/off switch.
 *
 * The row runs the toggle itself: the switch is disabled until `onToggle` settles, and a
 * rejection shows `toggleErrorMessage` inside the row.
 */
export function SettingsRow({
  name,
  active,
  statusLabel,
  badges,
  details,
  description,
  toggleLabel,
  onToggle,
  toggleErrorMessage,
  actions,
}: {
  name: string;
  active: boolean;
  statusLabel: string;
  badges?: ReactNode;
  details?: ReactNode;
  description?: ReactNode;
  toggleLabel: string;
  onToggle: (checked: boolean) => Promise<void>;
  toggleErrorMessage: (error: unknown, checked: boolean) => string;
  actions: ReactNode;
}) {
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async (checked: boolean) => {
    setToggling(true);
    setError(null);
    try {
      await onToggle(checked);
    } catch (err) {
      setError(toggleErrorMessage(err, checked));
    } finally {
      setToggling(false);
    }
  };

  return (
    <div
      role="listitem"
      className="flex flex-col sm:flex-row sm:items-center gap-3 px-4 py-4 border-b border-border last:border-b-0"
    >
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h3 className="font-medium text-foreground truncate">{name}</h3>
          {badges}
          <StatusBadge active={active} label={statusLabel} />
        </div>
        {details && (
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-muted-foreground">
            {details}
          </div>
        )}
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
        {error && <p className="mt-2 text-sm text-error-600 dark:text-error-400">{error}</p>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {actions}
        {/* The switch comes last, so every row's switch lines up whatever actions it has. */}
        <Switch
          checked={active}
          onCheckedChange={handleToggle}
          disabled={toggling}
          aria-label={toggleLabel}
        />
      </div>
    </div>
  );
}
