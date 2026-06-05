"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import { fetchRagSources } from "@/lib/slack-api";

interface DocSourcePickerProps {
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}

export default function DocSourcePicker({
  value,
  onChange,
  disabled = false,
}: DocSourcePickerProps) {
  const { token } = useAuth();
  const [sources, setSources] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRagSources(token);
      setSources(Array.isArray(data.sources) ? data.sources : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load RAG sources");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = useCallback(
    (source: string) => {
      onChange(value.includes(source) ? value.filter((s) => s !== source) : [...value, source]);
    },
    [value, onChange],
  );

  const selectAll = () => {
    if (loading) return;
    onChange([...sources]);
  };
  const clearAll = () => {
    if (loading) return;
    onChange([]);
  };

  if (loading) {
    return (
      <div className="w-full">
        <div className="block text-sm font-medium text-foreground mb-1.5">Allowed sources</div>
        <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
          <Spinner size="sm" />
          Loading sources…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full">
        <div className="block text-sm font-medium text-foreground mb-1.5">Allowed sources</div>
        <Alert severity="error" className="mb-2">
          <div className="flex items-center justify-between gap-3">
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={load}>
              <RefreshCw className="size-4 mr-1" aria-hidden="true" />
              Retry
            </Button>
          </div>
        </Alert>
      </div>
    );
  }

  if (sources.length === 0) {
    return (
      <div className="w-full">
        <div className="block text-sm font-medium text-foreground mb-1.5">Allowed sources</div>
        <Alert severity="info">
          No RAG sources yet. Import documents from Resources to restrict what this bot can answer
          from.
        </Alert>
      </div>
    );
  }

  return (
    <div className="w-full" role="group" aria-labelledby="doc-source-picker-label">
      <div className="flex items-center justify-between mb-1.5">
        <div id="doc-source-picker-label" className="block text-sm font-medium text-foreground">
          Allowed sources
        </div>
        <div className="flex items-center gap-3 text-xs">
          <button
            type="button"
            onClick={selectAll}
            disabled={disabled}
            className="text-primary-600 hover:underline disabled:opacity-50"
          >
            Select all
          </button>
          <button
            type="button"
            onClick={clearAll}
            disabled={disabled}
            className="text-primary-600 hover:underline disabled:opacity-50"
          >
            Clear
          </button>
        </div>
      </div>

      <ul className="max-h-48 overflow-y-auto border border-border rounded-lg divide-y divide-border">
        {sources.map((source) => {
          const isSelected = value.includes(source);
          return (
            <li key={source} className="px-3 py-2 hover:bg-surface-variant/50">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isSelected}
                  disabled={disabled}
                  onChange={() => toggle(source)}
                  className="size-4 rounded border-border cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <span className="text-sm text-foreground truncate">{source}</span>
              </label>
            </li>
          );
        })}
      </ul>

      {value.length === 0 ? (
        <p className="mt-1 text-xs text-muted-foreground">All sources allowed (no restriction).</p>
      ) : (
        <p className="mt-1 text-xs text-muted-foreground">
          {value.length} of {sources.length} sources selected.
        </p>
      )}
    </div>
  );
}
