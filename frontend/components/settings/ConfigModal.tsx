"use client";

import { useState, useMemo, useCallback } from "react";
import { Save } from "lucide-react";
import { UserPluginState } from "@/lib/plugins";
import { PluginConfigField } from "./ConfigField";
import { isUrlKey, isValidUrl } from "./utils";
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
  onSave: (config: Record<string, string>) => Promise<void>;
  onRefresh: () => void;
}

export function PluginConfigModal({
  plugin,
  open,
  onOpenChange,
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
      onOpenChange(false);
    } catch (err) {
      setSubmitError("Failed to save configuration.");
      console.error(String(err));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure {plugin.plugin_name}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4">
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

        <DialogFooter className="gap-3 border-t border-border pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
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
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
