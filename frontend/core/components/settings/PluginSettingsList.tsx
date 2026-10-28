"use client";

import { lazy, Suspense, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { PluginErrorBoundary } from "@/components/PluginErrorBoundary";
import { Spinner } from "@/core/components/ui/Spinner";
import { usePluginContext } from "@/core/plugins/context";
import type { UserPluginState } from "@/core/plugins/types";
import { SETTINGS_ITEMS, type SettingsItem } from "@/lib/settings/slots";
import { slotItems } from "@/lib/slots";
import { configFieldsOf } from "./schema";
import { SettingsList } from "./SettingsPage";

interface PluginSettingsRowProps {
  plugin: UserPluginState;
  item: SettingsItem;
}

/**
 * One plugin's row and, once the user first opens it, the config modal the plugin supplied. The row
 * offers the modal only while the plugin's backend config declares fields. A spinner shows while the
 * modal loads, and an error shows under the row if it fails to load.
 */
function PluginSettingsRow({ plugin, item }: PluginSettingsRowProps) {
  const { enablePlugin, disablePlugin, updatePluginConfig, refreshPlugins } = usePluginContext();
  const [open, setOpen] = useState(false);
  const [opened, setOpened] = useState(false);
  const ConfigModal = useMemo(
    () => (item.loadConfigModal ? lazy(item.loadConfigModal) : null),
    [item.loadConfigModal],
  );
  const ListItem = item.listItem;
  const configurable = ConfigModal !== null && configFieldsOf(plugin.config_schema).length > 0;
  const name = plugin.plugin_name;

  const configure = () => {
    setOpened(true);
    setOpen(true);
  };

  return (
    <>
      <ListItem
        plugin={plugin}
        onEnable={() => enablePlugin(name)}
        onDisable={() => disablePlugin(name)}
        onConfigure={configurable ? configure : undefined}
      />
      {ConfigModal && opened && (
        <PluginErrorBoundary pluginName={name}>
          <Suspense fallback={<Spinner size="sm" />}>
            <ConfigModal
              plugin={plugin}
              open={open}
              onOpenChange={setOpen}
              onSave={(config) => updatePluginConfig(name, config)}
              onRefresh={refreshPlugins}
            />
          </Suspense>
        </PluginErrorBoundary>
      )}
    </>
  );
}

/**
 * The settings page's plugin list: the row each plugin set in `SETTINGS_ITEMS`, for every
 * plugin the API returned, in plugin-name order.
 */
export function PluginSettingsList() {
  const t = useTranslations("plugins");
  const { userPlugins } = usePluginContext();
  const rows = slotItems(SETTINGS_ITEMS).flatMap(([name, item]) => {
    const plugin = userPlugins.find((candidate) => candidate.plugin_name === name);
    return plugin ? [{ plugin, item }] : [];
  });

  return (
    <SettingsList empty={<p className="text-muted-foreground">{t("empty")}</p>}>
      {rows.map(({ plugin, item }, index) => (
        <PluginSettingsRow key={`${plugin.plugin_name}-${index}`} plugin={plugin} item={item} />
      ))}
    </SettingsList>
  );
}
