"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Sliders } from "lucide-react";
import { displayNameOf } from "@/core/plugins/metadata";
import { UserPluginState } from "@/core/plugins/types";
import { PluginConfigModal } from "./ConfigModal";
import { SettingsRow } from "./SettingsRow";
import { Button } from "@/core/components/ui/Button";

interface PluginListItemProps {
  plugin: UserPluginState;
  onEnable: () => Promise<void>;
  onDisable: () => Promise<void>;
  onConfigChange: (config: Record<string, unknown>) => Promise<void>;
  onRefresh: () => void;
}

export default function PluginListItem({
  plugin,
  onEnable,
  onDisable,
  onConfigChange,
  onRefresh,
}: PluginListItemProps) {
  const t = useTranslations("plugins");
  const name = displayNameOf(plugin);
  const [showConfigModal, setShowConfigModal] = useState(false);

  return (
    <>
      <SettingsRow
        name={name}
        active={plugin.enabled}
        statusLabel={plugin.enabled ? t("enabled") : t("disabled")}
        description={plugin.display?.description}
        toggleLabel={t("toggle", { name })}
        onToggle={(checked) => (checked ? onEnable() : onDisable())}
        toggleErrorMessage={(_, checked) => (checked ? t("enableError") : t("disableError"))}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowConfigModal(true)}
            disabled={!plugin.enabled}
            aria-label={t("configure", { name })}
          >
            <Sliders className="h-4 w-4" aria-hidden="true" />
          </Button>
        }
      />
      {showConfigModal && (
        <PluginConfigModal
          plugin={plugin}
          open
          onOpenChange={setShowConfigModal}
          onSave={onConfigChange}
          onRefresh={onRefresh}
        />
      )}
    </>
  );
}
