"use client";

import { useMemo, useState, useCallback } from "react";
import {
  togglePlugin,
  upsertUserPluginConfig,
  UserPlugin,
} from "@/lib/user-plugins";
import { useAuth } from "@/lib/auth-context";

import { PluginHeader } from "./Header";
import { PluginConfig } from "./Config";
import { isUrlKey, isValidUrl } from "./utils";

interface PluginCardProps {
  plugin: UserPlugin;
  onUpdate: () => void;
}

export default function PluginCard({ plugin, onUpdate }: PluginCardProps) {
  const { token } = useAuth();

  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const [configValues, setConfigValues] = useState<Record<string, string>>(
    plugin.config ?? {}
  );

  const [errors, setErrorsState] = useState<Record<string, string>>({});

  const hasErrors = useMemo(() => {
    const emptyField = Object.values(configValues).some((v) => !v);
    const validationError = Object.values(errors).some(Boolean);
    return emptyField || validationError;
  }, [configValues, errors]);

  const handleConfigChange = useCallback((key: string, value: string) => {
    setConfigValues((prev) => ({ ...prev, [key]: value }));

    if (!isUrlKey(key)) return;

    setErrorsState((prev) => ({
      ...prev,
      [key]: isValidUrl(value) ? "" : "Input should be a valid URL",
    }));
  }, []);

  const handleSave = async () => {
    if (!token) {
      alert("You must be logged in.");
      return;
    }

    try {
      setIsSaving(true);

      await upsertUserPluginConfig(plugin.plugin_name, configValues, token);

      setIsEditing(false);
      onUpdate();
    } catch (err) {
      alert(`${err}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setConfigValues(plugin.config ?? {});
    setErrorsState({});
    setIsEditing(false);
  };

  const handleToggle = async () => {
    if (!token) return alert("You must be logged in.");
    const action = plugin.enabled ? "disable" : "enable";

    try {
      setIsToggling(true);
      await togglePlugin(plugin.plugin_name, action, token);
      onUpdate();
    } catch (err) {
      alert(err);
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
      />

      <PluginConfig
        config={configValues}
        errors={errors}
        setErrors={(key, msg) => {
          setErrorsState((prev) => ({ ...prev, [key]: msg }));
        }}
        isEditing={isEditing}
        isSaving={isSaving}
        hasErrors={hasErrors}
        onChange={handleConfigChange}
        onSave={handleSave}
        onCancel={handleCancel}
      />
    </div>
  );
}
