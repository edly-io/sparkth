"use client";

import { Save, X } from "lucide-react";
import { PluginConfigField } from "./ConfigField";

interface PluginConfigProps {
  config: Record<string, string | null>;
  errors: Record<string, string>;
  setErrors: (key: string, msg: string) => void;
  isEditing: boolean;
  isSaving: boolean;
  hasErrors: boolean;
  onChange: (key: string, value: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

export function PluginConfig({
  config,
  errors,
  setErrors,
  isEditing,
  isSaving,
  hasErrors,
  onChange,
  onSave,
  onCancel,
}: PluginConfigProps) {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-lg font-semibold text-gray-900">Configuration</h4>

        {isEditing && (
          <div className="flex gap-2">
            <button
              onClick={onSave}
              disabled={isSaving || hasErrors}
              className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg bg-green-600 hover:bg-green-700 text-white disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              Save
            </button>

            <button
              onClick={onCancel}
              className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-800"
            >
              <X className="w-4 h-4" />
              Cancel
            </button>
          </div>
        )}
      </div>

      {Object.keys(config).length > 0 ? (
        <div className="space-y-3">
          {Object.entries(config).map(([key, value]) => (
            <PluginConfigField
              key={key}
              name={key}
              value={value}
              isEditing={isEditing}
              error={errors[key]}
              onChange={onChange}
              setError={(field, msg) => {
                setErrors(field, msg);
              }}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500 italic">
          No configuration options available
        </p>
      )}
    </div>
  );
}
