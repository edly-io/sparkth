"use client";

import { useState, useEffect, useCallback } from "react";
import { Save } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { UserPluginState } from "@/lib/plugins";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Input } from "@/components/ui/Input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/Dialog";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ProviderInfo {
  id: string;
  label: string;
  models: string[];
}

interface ChatConfigModalProps {
  plugin: UserPluginState;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (config: Record<string, string>) => Promise<void>;
  onRefresh: () => void;
}

// ─── Select component (styled to match Input) ────────────────────────────────

interface SelectFieldProps {
  id: string;
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

function SelectField({
  id,
  label,
  value,
  options,
  onChange,
  disabled = false,
  placeholder,
}: SelectFieldProps) {
  return (
    <div className="w-full">
      <label
        htmlFor={id}
        className="block text-sm font-medium text-foreground mb-1.5"
      >
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(
          "appearance-none block w-full px-4 py-3 rounded-lg",
          "text-foreground bg-input",
          "border-2 border-border",
          "focus:outline-none focus:border-primary-500",
          "transition-colors",
          "disabled:opacity-50 disabled:cursor-not-allowed",
        )}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// ─── Main modal ──────────────────────────────────────────────────────────────

export default function ChatConfigModal({
  plugin,
  open,
  onOpenChange,
  onSave,
  onRefresh,
}: ChatConfigModalProps) {
  const { token } = useAuth();

  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [provider, setProvider] = useState<string>(
    (plugin.config?.provider as string) ?? "",
  );
  const [model, setModel] = useState<string>(
    (plugin.config?.model as string) ?? "",
  );
  const [apiKey, setApiKey] = useState<string>(
    (plugin.config?.api_key as string) ?? "",
  );

  const [isSaving, setIsSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // ── Fetch provider catalog when modal opens ─────────────────────────────

  const fetchProviders = useCallback(async () => {
    if (!token) return;
    setLoadingProviders(true);
    setFetchError(null);
    try {
      const res = await fetch("/api/v1/chat/providers", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed to load providers (${res.status})`);
      const data: { providers: ProviderInfo[] } = await res.json();
      setProviders(data.providers);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Could not load providers.");
    } finally {
      setLoadingProviders(false);
    }
  }, [token]);

  useEffect(() => {
    if (open) {
      fetchProviders();
      // Re-sync fields from plugin config each time the modal opens
      setProvider((plugin.config?.provider as string) ?? "");
      setModel((plugin.config?.model as string) ?? "");
      setApiKey((plugin.config?.api_key as string) ?? "");
      setSubmitError(null);
    }
  }, [open, fetchProviders, plugin.config]);

  // ── Keep model in sync when provider changes ────────────────────────────

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    const providerInfo = providers.find((p) => p.id === newProvider);
    // Reset model to first available model for the new provider
    setModel(providerInfo?.models[0] ?? "");
  };

  // ── Derived state ────────────────────────────────────────────────────────

  const availableModels =
    providers.find((p) => p.id === provider)?.models ?? [];

  const canSave =
    !isSaving &&
    !loadingProviders &&
    provider !== "" &&
    model !== "" &&
    apiKey !== "";

  // ── Save ─────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setSubmitError(null);
      await onSave({ provider, model, api_key: apiKey });
      onRefresh();
      onOpenChange(false);
    } catch {
      setSubmitError("Failed to save configuration. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────

  const providerOptions = providers.map((p) => ({ value: p.id, label: p.label }));
  const modelOptions = availableModels.map((m) => ({ value: m, label: m }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure {plugin.plugin_name}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {submitError && (
            <Alert severity="error">{submitError}</Alert>
          )}
          {fetchError && (
            <Alert severity="error">{fetchError}</Alert>
          )}

          <SelectField
            id="chat-provider"
            label="Provider"
            value={provider}
            options={providerOptions}
            onChange={handleProviderChange}
            disabled={loadingProviders}
            placeholder={loadingProviders ? "Loading providers…" : "Select a provider"}
          />

          <SelectField
            id="chat-model"
            label="Model"
            value={model}
            options={modelOptions}
            onChange={setModel}
            disabled={loadingProviders || provider === ""}
            placeholder="Select a model"
          />

          <Input
            id="chat-api-key"
            name="api_key"
            label="API Key"
            type="password"
            placeholder="Enter your API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoComplete="off"
          />
        </div>

        <DialogFooter className="gap-3 border-t border-border pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={!canSave}
            loading={isSaving}
            spinnerLabel="Saving"
          >
            <Save className="w-4 h-4 mr-2" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
