"use client";

import { lazy, Suspense, useMemo, useState } from "react";

import { usePluginContext } from "@/core/plugins/context";
import type { UserPluginState } from "@/core/plugins/types";
import { SETTINGS_ITEMS, type SettingsItem } from "@/lib/settings/slots";
import { slotItems } from "@/lib/slots";
import { configFieldsOf } from "./schema";

interface SettingsRowProps {
  plugin: UserPluginState;
  item: SettingsItem;
}

/**
 * One plugin's row and, once the user first opens it, the config modal the plugin supplied. The row
 * offers the modal only while the plugin's backend config declares fields.
 */
function SettingsRow({ plugin, item }: SettingsRowProps) {
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
        <Suspense fallback={null}>
          <ConfigModal
            plugin={plugin}
            open={open}
            onOpenChange={setOpen}
            onSave={(config) => updatePluginConfig(name, config)}
            onRefresh={refreshPlugins}
          />
        </Suspense>
      )}
    </>
  );
}

/**
 * The settings page's plugin list: the row each plugin set in `SETTINGS_ITEMS`, for every
 * plugin the API returned, in plugin-name order.
 */
export function SettingsList() {
  const { userPlugins } = usePluginContext();
  const rows = slotItems(SETTINGS_ITEMS).flatMap(([name, item]) => {
    const plugin = userPlugins.find((candidate) => candidate.plugin_name === name);
    return plugin ? [{ plugin, item }] : [];
  });

  if (rows.length === 0) {
    return (
      <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
        <p className="text-muted-foreground">No plugins found</p>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg shadow-sm overflow-hidden border border-border divide-y divide-border">
      {rows.map(({ plugin, item }, index) => (
        <SettingsRow key={`${plugin.plugin_name}-${index}`} plugin={plugin} item={item} />
      ))}
    </div>
  );
}
