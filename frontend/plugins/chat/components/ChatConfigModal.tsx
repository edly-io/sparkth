"use client";

import { useState, useEffect, useRef } from "react";
import { Save } from "lucide-react";
import { UserPluginState } from "@/lib/plugins";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Select } from "@/components/ui/Select";
import { LLMConfigSelect } from "@/components/LLMConfigSelect";
import { useAuth } from "@/lib/auth-context";
import { fetchProviderCatalog, type LLMConfig, type ProviderInfo } from "@/lib/llm-api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/Dialog";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatConfigModalProps {
  plugin: UserPluginState;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (config: Record<string, string>) => Promise<void>;
  onRefresh: () => void;
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

  const [llmConfigId, setLlmConfigId] = useState<number | undefined>(() => {
    const raw = plugin.config?.llm_config_id;
    const num = Number(raw);
    return raw != null && raw !== "" && !Number.isNaN(num) ? num : undefined;
  });
  const [modelOverride, setModelOverride] = useState<string>("");
  const [selectedConfig, setSelectedConfig] = useState<LLMConfig | undefined>(undefined);
  const [catalogProviders, setCatalogProviders] = useState<ProviderInfo[]>([]);
  const [providerModels, setProviderModels] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const prevOpenRef = useRef(open);

  // Reset form state when the modal opens.
  useEffect(() => {
    const justOpened = open && !prevOpenRef.current;
    prevOpenRef.current = open;
    if (!justOpened) return;

    const raw = plugin.config?.llm_config_id;
    const num = Number(raw);
    setLlmConfigId(raw != null && raw !== "" && !Number.isNaN(num) ? num : undefined);
    setModelOverride(
      typeof plugin.config?.llm_model_override === "string" ? plugin.config.llm_model_override : "",
    );
    setSubmitError(null);
  }, [open, plugin.config]);

  // Fetch the full provider catalog once per token — independent of selected config.
  useEffect(() => {
    if (!token) return;
    let ignore = false;
    fetchProviderCatalog(token)
      .then((catalog) => {
        if (!ignore) setCatalogProviders(catalog.providers);
      })
      .catch(() => {
        if (!ignore) setCatalogProviders([]);
      });
    return () => {
      ignore = true;
    };
  }, [token]);

  // Derive available models from the already-fetched catalog whenever the provider changes.
  useEffect(() => {
    if (!selectedConfig) {
      setProviderModels([]);
      return;
    }
    const info = catalogProviders.find((p) => p.id === selectedConfig.provider);
    setProviderModels(info?.models ?? []);
  }, [selectedConfig?.provider, catalogProviders]);

  const handleConfigSelect = (config: LLMConfig | undefined) => {
    setSelectedConfig(config);
    // Reset the override when the user actively picks a different config.
    if (config?.id !== llmConfigId) setModelOverride("");
  };

  const modelOptions = [
    { value: "", label: "Use config default" },
    ...providerModels.map((m) => ({ value: m, label: m })),
  ];

  const selectedIsInactive = selectedConfig !== undefined && !selectedConfig.is_active;
  const canSave = !isSaving && llmConfigId !== undefined && !selectedIsInactive;

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setSubmitError(null);
      const payload: Record<string, string> = {
        llm_config_id: String(llmConfigId),
      };
      if (modelOverride !== "") {
        payload.llm_model_override = modelOverride;
      }
      await onSave(payload);
      onRefresh();
      onOpenChange(false);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save configuration. Please try again.";
      setSubmitError(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure {plugin.plugin_name}</DialogTitle>
          <DialogDescription>
            Select an LLM configuration to use for this chat plugin.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {submitError && <Alert severity="error">{submitError}</Alert>}
          <LLMConfigSelect
            value={llmConfigId}
            onChange={setLlmConfigId}
            onConfigSelect={handleConfigSelect}
            required
            label="LLM Config"
          />
          <Select
            id="chat-model-override"
            name="llm_model_override"
            label="Model Override"
            value={modelOverride}
            options={modelOptions}
            onChange={(e) => setModelOverride(e.target.value)}
            disabled={!llmConfigId || selectedIsInactive || providerModels.length === 0}
            helperText={
              !llmConfigId
                ? "Select an LLM config first."
                : selectedIsInactive
                  ? "Reactivate this config in AI Keys to change the model."
                  : providerModels.length === 0
                    ? "Loading available models…"
                    : undefined
            }
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
