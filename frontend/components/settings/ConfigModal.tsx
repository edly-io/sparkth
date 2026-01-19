"use client";

import { useState, useMemo, useCallback } from "react";
import { X, Save } from "lucide-react";
import { UserPluginState } from "@/lib/plugins";
import { PluginConfigField } from "./ConfigField";
import { isUrlKey, isValidUrl } from "./utils";

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
    plugin.config ?? {}
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
      console.log(String(err));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-edly-gray-900">
            Configure {plugin.plugin_name}
          </h2>
          <button
            onClick={onClose}
            className="text-edly-gray-400 hover:text-edly-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {submitError && (
            <div className="mb-4 rounded-lg border border-edly-red-200 bg-edly-red-50 px-3 py-2 text-sm text-edly-red-700">
              {submitError}
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
            <p className="text-sm text-edly-gray-500 italic text-center py-8">
              No configuration options available
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 p-6 border-t bg-edly-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-edly-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-edly-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || hasErrors}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg enabled:hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Save className="w-4 h-4" />
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
