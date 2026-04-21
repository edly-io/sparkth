"use client";

import { useReducer, useEffect, useCallback, useRef } from "react";
import { ChevronDown, Save } from "lucide-react";
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

interface ConfigState {
  providers: ProviderInfo[];
  loadingProviders: boolean;
  fetchError: string | null;
  provider: string;
  model: string;
  apiKey: string;
  apiKeyChanged: boolean;
  isSaving: boolean;
  submitError: string | null;
}

type ConfigAction =
  | { type: "RESET_FOR_OPEN"; provider: string; model: string; apiKey: string }
  | { type: "FETCH_START" }
  | { type: "FETCH_SUCCESS"; providers: ProviderInfo[] }
  | { type: "FETCH_ERROR"; error: string }
  | { type: "FETCH_END" }
  | { type: "PROVIDERS_LOADED"; provider: string; model: string }
  | { type: "SET_PROVIDER"; provider: string; model: string }
  | { type: "SET_MODEL"; model: string }
  | { type: "SET_API_KEY"; apiKey: string }
  | { type: "SAVE_START" }
  | { type: "SAVE_ERROR"; error: string }
  | { type: "SAVE_END" };

function configReducer(state: ConfigState, action: ConfigAction): ConfigState {
  switch (action.type) {
    case "RESET_FOR_OPEN":
      return {
        ...state,
        provider: action.provider,
        model: action.model,
        apiKey: action.apiKey,
        apiKeyChanged: false,
        submitError: null,
      };
    case "FETCH_START":
      return { ...state, loadingProviders: true, fetchError: null };
    case "FETCH_SUCCESS":
      return { ...state, providers: action.providers };
    case "FETCH_ERROR":
      return { ...state, fetchError: action.error };
    case "FETCH_END":
      return { ...state, loadingProviders: false };
    case "PROVIDERS_LOADED":
      return { ...state, provider: action.provider, model: action.model };
    case "SET_PROVIDER":
      return { ...state, provider: action.provider, model: action.model };
    case "SET_MODEL":
      return { ...state, model: action.model };
    case "SET_API_KEY":
      return { ...state, apiKey: action.apiKey, apiKeyChanged: true };
    case "SAVE_START":
      return { ...state, isSaving: true, submitError: null };
    case "SAVE_ERROR":
      return { ...state, submitError: action.error };
    case "SAVE_END":
      return { ...state, isSaving: false };
  }
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
      <label htmlFor={id} className="block text-sm font-medium text-foreground mb-1.5">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className={cn(
            "appearance-none block w-full px-4 py-3 pr-10 rounded-lg",
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
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          size={16}
        />
      </div>
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

  const [state, dispatch] = useReducer(configReducer, {
    providers: [],
    loadingProviders: false,
    fetchError: null,
    provider: (plugin.config?.provider as string) ?? "",
    model: (plugin.config?.model as string) ?? "",
    apiKey: (plugin.config?.api_key as string) ?? "",
    apiKeyChanged: false,
    isSaving: false,
    submitError: null,
  });

  const {
    providers,
    loadingProviders,
    fetchError,
    provider,
    model,
    apiKey,
    apiKeyChanged,
    isSaving,
    submitError,
  } = state;

  const abortRef = useRef<AbortController | null>(null);

  const fetchProviders = useCallback(
    async (signal: AbortSignal) => {
      if (!token) return null;
      dispatch({ type: "FETCH_START" });
      try {
        const res = await fetch("/api/v1/chat/providers", {
          headers: { Authorization: `Bearer ${token}` },
          signal,
        });
        if (!res.ok) throw new Error(`Failed to load providers (${res.status})`);
        const data: { providers: ProviderInfo[]; default_provider: string; default_model: string } =
          await res.json();
        dispatch({ type: "FETCH_SUCCESS", providers: data.providers });
        return data;
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return null;
        dispatch({
          type: "FETCH_ERROR",
          error: err instanceof Error ? err.message : "Could not load providers.",
        });
        return null;
      } finally {
        dispatch({ type: "FETCH_END" });
      }
    },
    [token],
  );

  const prevOpenRef = useRef(open);

  useEffect(() => {
    const justOpened = open && !prevOpenRef.current;
    prevOpenRef.current = open;

    if (!justOpened) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const configProvider = (plugin.config?.provider as string) ?? "";
    const configModel = (plugin.config?.model as string) ?? "";
    dispatch({
      type: "RESET_FOR_OPEN",
      provider: configProvider,
      model: configModel,
      apiKey: (plugin.config?.api_key as string) ?? "",
    });
    fetchProviders(controller.signal).then((data) => {
      if (!data) return;
      if (!configProvider || !configModel) {
        dispatch({
          type: "PROVIDERS_LOADED",
          provider: configProvider || data.default_provider,
          model: configModel || data.default_model,
        });
      }
    });

    return () => controller.abort();
  }, [open, fetchProviders, plugin.config]);

  const handleProviderChange = (newProvider: string) => {
    const providerInfo = providers.find((p) => p.id === newProvider);
    dispatch({ type: "SET_PROVIDER", provider: newProvider, model: providerInfo?.models[0] ?? "" });
  };

  const availableModels = providers.find((p) => p.id === provider)?.models ?? [];

  const hasKey = apiKeyChanged || apiKey !== "";
  const canSave = !isSaving && !loadingProviders && provider !== "" && model !== "" && hasKey;

  const handleSave = async () => {
    try {
      dispatch({ type: "SAVE_START" });
      const payload: Record<string, string> = { provider, model };
      if (apiKeyChanged) {
        payload.api_key = apiKey;
      }
      await onSave(payload);
      onRefresh();
      onOpenChange(false);
    } catch {
      dispatch({ type: "SAVE_ERROR", error: "Failed to save configuration. Please try again." });
    } finally {
      dispatch({ type: "SAVE_END" });
    }
  };

  const providerOptions = providers.map((p) => ({ value: p.id, label: p.label }));
  const modelOptions = availableModels.map((m) => ({ value: m, label: m }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure {plugin.plugin_name}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {submitError && <Alert severity="error">{submitError}</Alert>}
          {fetchError && <Alert severity="error">{fetchError}</Alert>}

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
            onChange={(m) => dispatch({ type: "SET_MODEL", model: m })}
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
            onChange={(e) => dispatch({ type: "SET_API_KEY", apiKey: e.target.value })}
            autoComplete="off"
          />
        </div>

        <DialogFooter className="gap-3 border-t border-border pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!canSave} loading={isSaving} spinnerLabel="Saving">
            <Save className="w-4 h-4 mr-2" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
