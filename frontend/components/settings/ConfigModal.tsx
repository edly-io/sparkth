"use client";

import { useState, useMemo, useCallback } from "react";
import { X, Save } from "lucide-react";
import { UserPluginState } from "@/lib/plugins";
import { PluginConfigField } from "./ConfigField";
import { isUrlKey, isValidUrl } from "./utils";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

interface PluginConfigModalProps {
  plugin: UserPluginState;
  onClose: () => void;
  onSave: (config: Record<string, string>) => Promise<void>;
  onRefresh: () => void;
}

export function PluginConfigModal({
  plugin,
  onClose,
  onSave,
  onRefresh,
}: PluginConfigModalProps) {
  const [configValues, setConfigValues] = useState<Record<string, string>>(
    plugin.config ?? {},
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const hasErrors = useMemo(() => {
    const emptyField = Object.values(configValues).some((v) => !v);
    const validationError = Object.values(errors).some(Boolean);
    return emptyField || validationError;
  }, [configValues, errors]);

  const handleConfigChange = useCallback((key: string, value: string) => {
    setConfigValues((prev) => ({ ...prev, [key]: value }));

    if (!isUrlKey(key)) return;

    setErrors((prev) => ({
      ...prev,
      [key]: isValidUrl(value) ? "" : "Input should be a valid URL",
    }));
  }, []);

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setSubmitError(null);
      await onSave(configValues);
      onRefresh();
      onClose();
    } catch (err) {
      setSubmitError("Failed to save configuration.");
      console.error(String(err));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="text-xl font-semibold text-foreground">
            Configure {plugin.plugin_name}
          </h2>
          <button
            onClick={onClose}
            className="text-muted hover:text-foreground transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {submitError && (
            <div className="mb-4">
              <Alert severity="error">{submitError}</Alert>
            </div>
          )}

          {Object.keys(configValues).length > 0 ? (
            <div className="space-y-4">
              {Object.entries(configValues).map(([key, value]) => (
                <PluginConfigField
                  key={key}
                  name={key}
                  value={value}
                  error={errors[key]}
                  onChange={handleConfigChange}
                  setError={(field, msg) =>
                    setErrors((prev) => ({ ...prev, [field]: msg }))
                  }
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic text-center py-8">
              No configuration options available
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 p-6 border-t border-border bg-surface-variant">
          <Button variant="error" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || hasErrors}
            loading={isSaving}
            spinnerLabel="Saving"
          >
            <Save className="w-4 h-4 mr-2" />
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
}
