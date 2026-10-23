"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Save } from "lucide-react";
import { useTranslations } from "next-intl";

import { displayNameOf, type UserPluginState } from "@/lib/plugins";
import {
  configFieldsOf,
  initialValuesOf,
  payloadOf,
  validateField,
  validateFields,
} from "@/lib/plugins/schema";
import { getConfigWidget } from "./widgets";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/Dialog";

interface PluginConfigModalProps {
  plugin: UserPluginState;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (config: Record<string, unknown>) => Promise<void>;
  onRefresh: () => void;
}

/**
 * The settings form for any plugin, built from the config schema it declared.
 *
 * Every field, its control, its validation and the types it saves come from the
 * backend's `config_schema`, so a plugin needs no frontend code to be configurable.
 * A stored secret shows as dots with a Replace action, and is neither validated nor
 * sent until replaced.
 */
export function PluginConfigModal({
  plugin,
  open,
  onOpenChange,
  onSave,
  onRefresh,
}: PluginConfigModalProps) {
  const fields = useMemo(() => configFieldsOf(plugin.config_schema), [plugin.config_schema]);

  const t = useTranslations("plugins.config");
  const stored = useMemo(() => new Set(plugin.secrets_set), [plugin.secrets_set]);
  const [replacing, setReplacing] = useState<Set<string>>(new Set());
  // A stored secret the user hasn't chosen to replace is neither validated nor sent.
  const editable = useMemo(
    () => fields.filter((field) => !stored.has(field.name) || replacing.has(field.name)),
    [fields, stored, replacing],
  );

  const [values, setValues] = useState<Record<string, unknown>>(() =>
    initialValuesOf(fields, plugin.config),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Reopening shows what is stored, not what was typed and abandoned last time.
  useEffect(() => {
    if (!open) return;
    setValues(initialValuesOf(fields, plugin.config));
    setErrors({});
    setSubmitError(null);
    setReplacing(new Set());
  }, [open, fields, plugin.config]);

  const handleChange = useCallback(
    (name: string, value: unknown) => {
      setValues((previous) => ({ ...previous, [name]: value }));

      const field = fields.find((candidate) => candidate.name === name);
      if (!field) return;
      setErrors((previous) => ({ ...previous, [name]: validateField(field, value) ?? "" }));
    },
    [fields],
  );

  const handleSave = async () => {
    const nextErrors = validateFields(editable, values);
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    try {
      setIsSaving(true);
      setSubmitError(null);
      await onSave(payloadOf(editable, values));
      onRefresh();
      onOpenChange(false);
    } catch (err) {
      setSubmitError(t("saveError"));
      console.error(String(err));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{t("title", { name: displayNameOf(plugin) })}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4">
          {submitError && (
            <div className="mb-4">
              <Alert severity="error">{submitError}</Alert>
            </div>
          )}

          {fields.length > 0 ? (
            <div className="space-y-5">
              {fields.map((field) => {
                if (!editable.includes(field)) {
                  return (
                    <div key={field.name}>
                      <p className="text-sm font-medium leading-none text-foreground">
                        {field.label}
                      </p>
                      <div className="mt-1.5 flex items-center gap-3">
                        <span
                          className="font-mono text-sm text-muted-foreground"
                          title={t("stored")}
                        >
                          ••••••••
                        </span>
                        <Button
                          variant="outline"
                          size="sm"
                          aria-label={t("replaceField", { field: field.label })}
                          onClick={() => setReplacing((prev) => new Set(prev).add(field.name))}
                        >
                          {t("replace")}
                        </Button>
                      </div>
                    </div>
                  );
                }
                const Widget = getConfigWidget(field.widget);
                return (
                  <Widget
                    key={field.name}
                    field={field}
                    value={values[field.name]}
                    values={values}
                    fields={fields}
                    error={errors[field.name] || undefined}
                    disabled={isSaving}
                    onChange={handleChange}
                  />
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic text-center py-8">{t("empty")}</p>
          )}
        </div>

        <DialogFooter className="gap-3 border-t border-border pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("cancel")}
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving}
            loading={isSaving}
            spinnerLabel={t("saving")}
          >
            <Save className="w-4 h-4 mr-2" />
            {t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
