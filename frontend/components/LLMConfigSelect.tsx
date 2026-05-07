"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { Select } from "@/components/ui/Select";
import { Alert } from "@/components/ui/Alert";
import { useAuth } from "@/lib/auth-context";
import { fetchLLMConfigs, type LLMConfig } from "@/lib/llm-api";

interface LLMConfigSelectProps {
  value: number | undefined;
  onChange: (configId: number) => void;
  onConfigSelect?: (config: LLMConfig | undefined) => void;
  disabled?: boolean;
  required?: boolean;
  label?: string;
  error?: string;
  id?: string;
}

export function LLMConfigSelect({
  value,
  onChange,
  onConfigSelect,
  disabled,
  required,
  label,
  error,
  id,
}: LLMConfigSelectProps) {
  const { token } = useAuth();
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");

  useEffect(() => {
    let ignore = false;

    if (!token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setFetchError("");

    fetchLLMConfigs(token)
      .then((result) => {
        if (!ignore) setConfigs(result.configs);
      })
      .catch((e) => {
        if (!ignore) setFetchError(e instanceof Error ? e.message : "Failed to load LLM configs");
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  const selectedConfig = configs.find((c) => c.id === value);
  const selectedIsInactive = selectedConfig !== undefined && !selectedConfig.is_active;

  // Notify parent when the resolved config object changes (on load or user selection).
  useEffect(() => {
    if (!loading) onConfigSelect?.(selectedConfig);
  }, [selectedConfig?.id, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  const options = configs.map((c) => ({
    value: String(c.id),
    label: c.is_active ? `${c.name} (${c.provider})` : `${c.name} (${c.provider}) — Deactivated`,
  }));

  if (!loading && !fetchError && configs.length === 0) {
    return (
      <div className="w-full">
        <label className="block text-sm font-medium text-foreground mb-1.5">
          {label ?? "LLM Config"}
        </label>
        <p className="text-sm text-muted-foreground">
          No LLM configs available.{" "}
          <Link
            href="/dashboard/llm/configure/new/"
            className="text-primary-500 hover:text-primary-600 underline"
          >
            Create one
          </Link>{" "}
          to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-2">
      <Select
        id={id || "llm-config-select"}
        label={label ?? "LLM Config"}
        value={value !== undefined ? String(value) : ""}
        options={options}
        onChange={(e) => {
          if (e.target.value === "") return;
          const parsed = Number(e.target.value);
          if (!Number.isNaN(parsed)) {
            onChange(parsed);
            onConfigSelect?.(configs.find((c) => c.id === parsed));
          }
        }}
        disabled={disabled || loading}
        placeholder={loading ? "Loading configs…" : "Select a config"}
        error={error || fetchError || undefined}
        required={required}
      />
      {selectedIsInactive && (
        <Alert severity="warning">
          This configuration is deactivated. Go to{" "}
          <Link href="/dashboard/llm/configure" className="underline font-medium">
            AI Keys
          </Link>{" "}
          to reactivate it, or select a different configuration.
        </Alert>
      )}
    </div>
  );
}
