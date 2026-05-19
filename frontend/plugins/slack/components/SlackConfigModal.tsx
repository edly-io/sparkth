"use client";

import { useState, useEffect } from "react";
import { Save } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Alert } from "@/components/ui/Alert";
import { Select } from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/Dialog";
import { Label } from "@/components/ui/Label";
import { LLMConfigSelect } from "@/components/LLMConfigSelect";
import { fetchProviderCatalog, type LLMConfig, type ProviderInfo } from "@/lib/llm-api";
import type { UserPluginState } from "@/lib/plugins";
import DocSourcePicker from "./DocSourcePicker";

const DEFAULTS = {
  bot_name: "TA Bot",
  fallback_message:
    "I couldn't find an answer in the course material. Please contact your instructor.",
  greeting_message: "Hello! I'm your TA Bot. How can I help you?",
  llm_temperature: 0.3,
};

interface SlackConfigModalProps {
  plugin: UserPluginState;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (config: Record<string, unknown>) => Promise<void>;
  onRefresh: () => void;
}

export default function SlackConfigModal({
  plugin,
  open,
  onOpenChange,
  onSave,
  onRefresh,
}: SlackConfigModalProps) {
  const { token } = useAuth();

  const [botName, setBotName] = useState(DEFAULTS.bot_name);
  const [fallbackMessage, setFallbackMessage] = useState(DEFAULTS.fallback_message);
  const [greetingMessage, setGreetingMessage] = useState(DEFAULTS.greeting_message);
  const [allowedSources, setAllowedSources] = useState<string[]>([]);

  const [synthesisEnabled, setSynthesisEnabled] = useState(true);
  const [llmTemperature, setLlmTemperature] = useState(DEFAULTS.llm_temperature);
  const [llmConfigId, setLlmConfigId] = useState<number | undefined>(undefined);
  const [modelOverride, setModelOverride] = useState("");
  const [selectedConfig, setSelectedConfig] = useState<LLMConfig | undefined>(undefined);
  const [catalogProviders, setCatalogProviders] = useState<ProviderInfo[]>([]);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const cfg = plugin.config ?? {};
    setBotName(cfg.bot_name ?? DEFAULTS.bot_name);
    setFallbackMessage(cfg.fallback_message ?? DEFAULTS.fallback_message);
    setGreetingMessage(cfg.greeting_message ?? DEFAULTS.greeting_message);

    // allowed_sources may be a JSONB array or a JSON-encoded string
    try {
      const raw = cfg.allowed_sources;
      const parsed = Array.isArray(raw) ? raw : raw ? JSON.parse(raw) : [];
      setAllowedSources(
        Array.isArray(parsed) ? parsed.filter((s): s is string => typeof s === "string") : [],
      );
    } catch {
      setAllowedSources([]);
    }

    const savedConfigId = cfg.llm_config_id;
    const savedConfigIdNum =
      savedConfigId === undefined || savedConfigId === "" ? undefined : Number(savedConfigId);

    const resolvedConfigId = Number.isFinite(savedConfigIdNum) ? savedConfigIdNum : undefined;
    setLlmConfigId(resolvedConfigId);
    setSynthesisEnabled(resolvedConfigId !== undefined);
    const savedTemp = cfg.llm_temperature;
    setLlmTemperature(
      savedTemp !== undefined && savedTemp !== "" && Number.isFinite(Number(savedTemp))
        ? Number(savedTemp)
        : DEFAULTS.llm_temperature,
    );
    setModelOverride(cfg.llm_model_override ?? "");
    setErrors({});
    setSubmitError(null);
  }, [open, plugin.config]);

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

  const providerModels =
    catalogProviders.find((p) => p.id === selectedConfig?.provider)?.models ?? [];

  const modelOptions = [
    { value: "", label: "Use config default" },
    ...providerModels.map((m) => ({ value: m, label: m })),
  ];

  const handleSave = async () => {
    const nextErrors: Record<string, string> = {};
    if (!botName.trim()) nextErrors.botName = "Bot name is required.";
    if (!fallbackMessage.trim()) nextErrors.fallbackMessage = "Fallback message is required.";
    if (!greetingMessage.trim()) nextErrors.greetingMessage = "Greeting message is required.";
    if (synthesisEnabled && llmConfigId === undefined)
      nextErrors.llmConfig = "Select an LLM config or disable synthesis.";

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      setSubmitError("Please fix the errors above and try again.");
      return;
    }

    setIsSaving(true);
    setSubmitError(null);
    try {
      const temperature = llmTemperature;

      const payload: Record<string, unknown> = {
        bot_name: botName.trim(),
        fallback_message: fallbackMessage.trim(),
        greeting_message: greetingMessage.trim(),
        allowed_sources: allowedSources,
        llm_config_id: synthesisEnabled ? llmConfigId : null,
        llm_temperature: temperature,
        llm_model_override: synthesisEnabled && modelOverride !== "" ? modelOverride : null,
      };
      await onSave(payload);
      onRefresh();
      onOpenChange(false);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to save configuration. Please try again.",
      );
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
            Configure the Slack TA Bot. Required fields are marked with *.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 space-y-5">
          {submitError && <Alert severity="error">{submitError}</Alert>}

          <Input
            id="slack-bot-name"
            label="Bot name"
            value={botName}
            onChange={(e) => setBotName(e.target.value)}
            error={errors.botName}
            required
          />

          <Textarea
            id="slack-fallback"
            label="Fallback message"
            value={fallbackMessage}
            onChange={(e) => setFallbackMessage(e.target.value)}
            error={errors.fallbackMessage}
            helperText="Sent when the bot can't find an answer in the course material."
            required
          />

          <Textarea
            id="slack-greeting"
            label="Greeting message"
            value={greetingMessage}
            onChange={(e) => setGreetingMessage(e.target.value)}
            error={errors.greetingMessage}
            helperText="Sent in response to casual greetings (e.g., 'hi')."
            required
          />

          <DocSourcePicker
            value={allowedSources}
            onChange={setAllowedSources}
            disabled={isSaving}
          />

          <div className="border-t border-border pt-5">
            <div className="flex items-center justify-between mb-3">
              <Label htmlFor="slack-synthesis-toggle">Enable LLM synthesis</Label>
              <Switch
                id="slack-synthesis-toggle"
                checked={synthesisEnabled}
                onCheckedChange={setSynthesisEnabled}
              />
            </div>
            <p className="text-xs text-muted-foreground mb-3">
              When enabled, the bot synthesizes answers using your selected LLM. When disabled, the
              bot returns raw RAG matches or the fallback message.
            </p>

            {synthesisEnabled && (
              <div className="space-y-3">
                <LLMConfigSelect
                  value={llmConfigId}
                  onChange={setLlmConfigId}
                  onConfigSelect={setSelectedConfig}
                  required
                  label="LLM config"
                  error={errors.llmConfig}
                />
                <Select
                  id="slack-model-override"
                  name="llm_model_override"
                  label="Model override"
                  value={modelOverride}
                  options={modelOptions}
                  onChange={(e) => setModelOverride(e.target.value)}
                  disabled={!llmConfigId || providerModels.length === 0}
                  helperText={
                    !llmConfigId
                      ? "Select an LLM config first."
                      : providerModels.length === 0
                        ? "Loading available models…"
                        : "Optionally override the model from the selected config."
                  }
                />
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="gap-3 border-t border-border pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving} loading={isSaving} spinnerLabel="Saving">
            <Save className="w-4 h-4 mr-2" aria-hidden="true" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
