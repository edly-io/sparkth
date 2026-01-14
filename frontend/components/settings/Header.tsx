"use client";

import { UserPluginState } from "@/lib/plugins";
import { Power, Pencil } from "lucide-react";

interface PluginHeaderProps {
  plugin: UserPluginState;
  isEditing: boolean;
  isToggling: boolean;
  onToggle: () => void;
  onEdit: () => void;
  toggleError?: string | null;
}

export function PluginHeader({
  plugin,
  isEditing,
  isToggling,
  onToggle,
  onEdit,
  toggleError,
}: PluginHeaderProps) {
  return (
    <div
      className={`p-6 border-b ${
        plugin.enabled ? "bg-green-50" : "bg-gray-50"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-xl font-semibold text-gray-900">
              {plugin.plugin_name}
            </h3>

            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                plugin.enabled
                  ? "bg-green-100 text-green-800"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {plugin.enabled ? "Enabled" : "Disabled"}
            </span>
          </div>

          <div className="text-xs text-gray-500">
            Type:{" "}
            <span className="font-medium text-gray-700">
              {plugin.is_core ? "Core" : "Custom"}
            </span>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={onToggle}
            disabled={isToggling}
            className={`p-2 rounded-lg transition-colors ${
              plugin.enabled
                ? "bg-green-600 hover:bg-green-700"
                : "bg-gray-400 hover:bg-gray-500"
            } text-white disabled:opacity-50`}
            aria-busy={isToggling}
          >
            <Power className="w-4 h-4" />
          </button>

          {!isEditing && (
            <button
              onClick={onEdit}
              disabled={!plugin.enabled}
              className={`p-2 rounded-lg ${
                plugin.enabled ? "bg-blue-600 hover:bg-blue-700" : "bg-gray-400"
              } text-white disabled:opacity-50`}
            >
              <Pencil className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {toggleError && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {toggleError}
        </div>
      )}
    </div>
  );
}
