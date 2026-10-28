"use client";

import { useTranslations } from "next-intl";
import { Sliders } from "lucide-react";
import { displayNameOf } from "@/core/plugins/metadata";
import type { SettingsListItemProps } from "@/lib/settings/slots";
import { Button } from "@/core/components/ui/Button";
import { SettingsRow } from "./SettingsRow";

/**
 * A plugin's row on the settings page: its name, description, status and on/off switch and, when
 * the plugin has a config modal, the button that opens it.
 */
export function SettingsListItem({
  plugin,
  onEnable,
  onDisable,
  onConfigure,
}: SettingsListItemProps) {
  const t = useTranslations("plugins");
  const name = displayNameOf(plugin);

  return (
    <SettingsRow
      name={name}
      active={plugin.enabled}
      statusLabel={plugin.enabled ? t("enabled") : t("disabled")}
      description={plugin.display?.description}
      toggleLabel={t("toggle", { name })}
      onToggle={(checked) => (checked ? onEnable() : onDisable())}
      toggleErrorMessage={(_, checked) => (checked ? t("enableError") : t("disableError"))}
      actions={
        onConfigure && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onConfigure}
            disabled={!plugin.enabled}
            aria-label={t("configure", { name })}
          >
            <Sliders className="h-4 w-4" aria-hidden="true" />
          </Button>
        )
      }
    />
  );
}
