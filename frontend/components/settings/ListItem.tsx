"use client";

import { useState } from "react";
import { Sliders } from "lucide-react";
import { getPlugin, UserPluginState } from "@/lib/plugins";
import { PluginConfigModal } from "./ConfigModal";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";

interface PluginListItemProps {
  plugin: UserPluginState;
  isLast: boolean;
  onEnable: () => Promise<void>;
  onDisable: () => Promise<void>;
  onConfigChange: (config: Record<string, string>) => Promise<void>;
  onRefresh: () => void;
}

export default function PluginListItem({
  plugin,
  isLast,
  onEnable,
  onDisable,
  onConfigChange,
  onRefresh,
}: PluginListItemProps) {
  const [isToggling, setIsToggling] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const pluginDef = getPlugin(plugin.plugin_name);

  const handleToggle = async () => {
    try {
      setIsToggling(true);
      setToggleError(null);
      if (plugin.enabled) await onDisable();
      else await onEnable();
      onRefresh();
    } catch (err) {
      console.error(String(err));
      setToggleError(
        `Failed to ${plugin.enabled ? "disable" : "enable"} the plugin.`,
      );
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <>
      <div className={`p-6 ${!isLast ? "border-b border-border" : ""}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-semibold text-foreground">
                {plugin.plugin_name}
              </h3>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  plugin.enabled
                    ? "bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400"
                    : "bg-neutral-200 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400"
                }`}
              >
                {plugin.enabled ? "Connected" : "Disconnected"}
              </span>
            </div>
            <p className="text-sm text-muted mb-2">Sparkth</p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {pluginDef?.description || plugin.description}
            </p>

            {toggleError && (
              <div className="mt-3 text-sm text-error-600 dark:text-error-400">
                {toggleError}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <Switch
              checked={plugin.enabled}
              onCheckedChange={handleToggle}
              disabled={isToggling}
            />

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowConfigModal(true)}
              disabled={!plugin.enabled}
              className="p-2 text-primary-600 dark:text-primary-400"
              title="Configure plugin"
            >
              <Sliders className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </div>

      <PluginConfigModal
        plugin={plugin}
        open={showConfigModal}
        onOpenChange={setShowConfigModal}
        onSave={onConfigChange}
        onRefresh={onRefresh}
      />
    </>
  );
}
