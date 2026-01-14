"use client";

import { useMemo, useState, useCallback, useEffect } from "react";

import { PluginHeader } from "./Header";
import { PluginConfig } from "./Config";
import { isUrlKey, isValidUrl } from "./utils";
import { UserPluginState } from "@/lib/plugins";

interface PluginCardProps {
  plugin: UserPluginState;
  onEnable: () => Promise<void>;
  onDisable: () => Promise<void>;
  onConfigChange: (config: Record<string, string>) => Promise<void>;
  onRefresh: () => void;
}

export default function PluginCard({
  plugin,
  onEnable,
  onDisable,
  onConfigChange,
  onRefresh,
}: PluginCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

  const [configValues, setConfigValues] = useState<Record<string, string>>(
    plugin.config ?? {}
  );

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setConfigValues(plugin.config ?? {});
    setErrors({});
    setIsEditing(false);
  }, [plugin]);

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
      await onConfigChange(configValues);
      setIsEditing(false);
      onRefresh();
    } catch (err) {
      setSubmitError("Failed to save configuration.");
      console.log(String(err));
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setConfigValues(plugin.config ?? {});
    setErrors({});
    setIsEditing(false);
    setSubmitError(null);
    setToggleError(null);
  };

  const handleToggle = async () => {
    try {
      setIsToggling(true);
      if (plugin.enabled) await onDisable();
      else await onEnable();
      onRefresh();
    } catch (err) {
      console.log(String(err));
      setToggleError(
        `Failed to ${plugin.enabled ? "disable" : "enable"} the plugin.`
      );
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="border rounded-lg shadow-sm overflow-hidden bg-white">
      <PluginHeader
        plugin={plugin}
        isEditing={isEditing}
        isToggling={isToggling}
        onToggle={handleToggle}
        onEdit={() => setIsEditing(true)}
        toggleError={toggleError}
      />

      <PluginConfig
        config={configValues}
        errors={errors}
        setErrors={(key, msg) => setErrors((prev) => ({ ...prev, [key]: msg }))}
        isEditing={isEditing}
        isSaving={isSaving}
        hasErrors={hasErrors}
        onChange={handleConfigChange}
        onSave={handleSave}
        onCancel={handleCancel}
        submitError={submitError}
      />
    </div>
  );
}
