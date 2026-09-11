"use client";

/**
 * The controls the generic settings modal renders config fields with.
 *
 * A field names its control through the `widget` hint on its Pydantic field
 * (`sparkth/core/plugins/widgets.py`); the modal looks that name up here. The plain
 * controls below cover every field whose JSON-schema type says enough on its own.
 * A widget that needs data the frontend must fetch — the user's LLM configs, their
 * RAG sources — is registered by the plugin that owns it, the way plugin icons are
 * (see `registerPluginIcon`), so core carries no plugin-specific fetching.
 *
 * An unknown widget name falls back to a text input rather than rendering nothing:
 * a backend that declares a hint this frontend has not shipped yet still gets a
 * usable field.
 */

import { ComponentType, useEffect, useState } from "react";

import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import { Label } from "@/components/ui/Label";
import { LLMConfigSelect } from "@/components/LLMConfigSelect";
import { useAuth } from "@/lib/auth-context";
import {
  fetchLLMConfigs,
  fetchProviderCatalog,
  type LLMConfig,
  type ProviderInfo,
} from "@/lib/llm";
import type { ConfigFieldDescriptor } from "@/lib/plugins/schema";

export interface ConfigWidgetProps {
  field: ConfigFieldDescriptor;
  value: unknown;
  /** Every field's current value, for a widget that depends on a sibling. */
  values: Record<string, unknown>;
  /** Every field, so a dependent widget can find its sibling by widget name. */
  fields: ConfigFieldDescriptor[];
  error?: string;
  disabled?: boolean;
  onChange: (name: string, value: unknown) => void;
}

export type ConfigWidgetComponent = ComponentType<ConfigWidgetProps>;

const registry = new Map<string, ConfigWidgetComponent>();

/** Register the control that renders fields hinting `name`. */
export function registerConfigWidget(name: string, component: ConfigWidgetComponent): void {
  registry.set(name, component);
}

export function getConfigWidget(name: string): ConfigWidgetComponent {
  return registry.get(name) ?? TextWidget;
}

/** The value of the sibling field rendered by `widget`, for dependent widgets. */
export function siblingValue(props: ConfigWidgetProps, widget: string): unknown {
  const sibling = props.fields.find((field) => field.widget === widget);
  return sibling ? props.values[sibling.name] : undefined;
}

const asText = (value: unknown) => (value === null || value === undefined ? "" : String(value));

function TextWidget({ field, value, error, disabled, onChange }: ConfigWidgetProps) {
  const isUrl = field.widget === "url";
  return (
    <Input
      id={`config-${field.name}`}
      name={field.name}
      label={field.label}
      type={field.widget === "password" ? "password" : isUrl ? "url" : "text"}
      inputMode={isUrl ? "url" : "text"}
      placeholder={isUrl ? "https://example.com" : undefined}
      value={asText(value)}
      onChange={(e) => onChange(field.name, e.target.value)}
      error={error}
      helperText={field.description}
      disabled={disabled}
      required={field.required}
    />
  );
}

function NumberWidget({ field, value, error, disabled, onChange }: ConfigWidgetProps) {
  return (
    <Input
      id={`config-${field.name}`}
      name={field.name}
      label={field.label}
      type="number"
      inputMode="decimal"
      min={field.minimum}
      max={field.maximum}
      step={field.type === "integer" ? 1 : "any"}
      value={asText(value)}
      onChange={(e) => onChange(field.name, e.target.value)}
      error={error}
      helperText={field.description}
      disabled={disabled}
      required={field.required}
    />
  );
}

function TextareaWidget({ field, value, error, disabled, onChange }: ConfigWidgetProps) {
  return (
    <Textarea
      id={`config-${field.name}`}
      name={field.name}
      label={field.label}
      value={asText(value)}
      onChange={(e) => onChange(field.name, e.target.value)}
      error={error}
      helperText={field.description}
      disabled={disabled}
      required={field.required}
    />
  );
}

function CheckboxWidget({ field, value, disabled, onChange }: ConfigWidgetProps) {
  return (
    <div className="w-full">
      <div className="flex items-center justify-between">
        <Label htmlFor={`config-${field.name}`}>{field.label}</Label>
        <Switch
          id={`config-${field.name}`}
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(field.name, checked)}
          disabled={disabled}
        />
      </div>
      {field.description && (
        <p className="mt-1.5 text-sm text-muted-foreground">{field.description}</p>
      )}
    </div>
  );
}

registerConfigWidget("text", TextWidget);
registerConfigWidget("url", TextWidget);
registerConfigWidget("password", TextWidget);
registerConfigWidget("number", NumberWidget);
registerConfigWidget("textarea", TextareaWidget);
registerConfigWidget("checkbox", CheckboxWidget);

// ─── LLM widgets ─────────────────────────────────────────────────────────────
// Core rather than plugin-owned: an `llm_config_id` reference is a shared plugin
// pattern (see LLMConfigAdapter), and both controls are built from core modules.

function LLMConfigWidget({ field, value, error, disabled, onChange }: ConfigWidgetProps) {
  const selected = Number(value);
  return (
    <LLMConfigSelect
      id={`config-${field.name}`}
      label={field.label}
      value={Number.isFinite(selected) && selected > 0 ? selected : undefined}
      onChange={(configId) => onChange(field.name, configId ?? "")}
      allowNone={field.nullable}
      required={field.required}
      error={error}
      disabled={disabled}
      helperText={field.description}
    />
  );
}

function LLMModelWidget(props: ConfigWidgetProps) {
  const { field, value, error, disabled, onChange } = props;
  const { token } = useAuth();
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);

  const configId = Number(siblingValue(props, "llm-config"));
  const hasConfig = Number.isFinite(configId) && configId > 0;

  useEffect(() => {
    if (!token) return;
    let ignore = false;
    Promise.all([fetchLLMConfigs(token, { includeInactive: true }), fetchProviderCatalog(token)])
      .then(([configResult, catalog]) => {
        if (ignore) return;
        setConfigs(configResult.configs);
        setProviders(catalog.providers);
      })
      .catch(() => {
        if (!ignore) setProviders([]);
      });
    return () => {
      ignore = true;
    };
  }, [token]);

  // The backend rejects a model override with no LLM config behind it, since the
  // provider is what makes a model name meaningful.
  useEffect(() => {
    if (!hasConfig && value !== "") onChange(field.name, "");
  }, [hasConfig, value, field.name, onChange]);

  const provider = configs.find((config) => config.id === configId)?.provider;
  const models = providers.find((entry) => entry.id === provider)?.models ?? [];

  const helperText = !hasConfig
    ? "Select an LLM config first."
    : models.length === 0
      ? "Loading available models…"
      : field.description;

  return (
    <Select
      id={`config-${field.name}`}
      name={field.name}
      label={field.label}
      value={asText(value)}
      options={[
        { value: "", label: "Use config default" },
        ...models.map((model) => ({ value: model, label: model })),
      ]}
      onChange={(e) => onChange(field.name, e.target.value)}
      disabled={disabled || !hasConfig || models.length === 0}
      helperText={helperText}
      error={error}
    />
  );
}

registerConfigWidget("llm-config", LLMConfigWidget);
registerConfigWidget("llm-model", LLMModelWidget);
