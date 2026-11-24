"use client";

import { useTranslations } from "next-intl";
import { Sliders } from "lucide-react";
import { displayNameOf } from "@/core/plugins/metadata";
import type { SettingsListItemProps } from "@/lib/settings/slots";
import { Button } from "@/core/components/ui/Button";
import { Spinner } from "@/core/components/ui/Spinner";
import { SettingsRow } from "@/core/settings/components/ui/SettingsRow";

/**
 * A plugin's row on the settings page: its name, description, masked keys, status and on/off
 * switch and, when the plugin has a config modal, the button that opens it. The button shows a
 * spinner while the modal loads.
 *
 * A plugin an administrator switched off system-wide shows that as its status. Its switch stays
 * at the user's own preference but cannot be used, and the configure button is disabled.
 */
export function SettingsListItem({
  plugin,
  onEnable,
  onDisable,
  onConfigure,
  configuring,
}: SettingsListItemProps) {
  const t = useTranslations("plugins");
  const name = displayNameOf(plugin);
  const masked = Object.entries(plugin.masked_secrets);
  const systemEnabled = plugin.system_enabled;
  const statusLabel = !systemEnabled
    ? t("disabledByAdmin")
    : plugin.enabled
      ? t("enabled")
      : t("disabled");

  return (
    <SettingsRow
      name={name}
      active={systemEnabled && plugin.enabled}
      statusLabel={statusLabel}
      description={plugin.display?.description}
      details={
        masked.length > 0 &&
        masked.map(([field, value]) => (
          <span key={field} className="font-mono">
            {value}
          </span>
        ))
      }
      toggleLabel={t("toggle", { name })}
      toggleChecked={plugin.enabled}
      toggleDisabled={!systemEnabled}
      onToggle={(checked) => (checked ? onEnable() : onDisable())}
      toggleErrorMessage={(_, checked) => (checked ? t("enableError") : t("disableError"))}
      actions={
        onConfigure && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onConfigure}
            disabled={!systemEnabled || !plugin.enabled || configuring}
            aria-busy={configuring}
            aria-label={t("configure", { name })}
          >
            {configuring ? (
              <Spinner size="sm" />
            ) : (
              <Sliders className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>
        )
      }
    />
  );
}
