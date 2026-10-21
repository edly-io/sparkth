"use client";

import { useTranslations } from "next-intl";
import PluginListItem from "@/components/settings/ListItem";
import { SettingsList, SettingsPage } from "@/components/settings/SettingsPage";
import { usePluginContext } from "@/lib/plugins/context";

export default function PluginsSettings() {
  const t = useTranslations("plugins");
  const {
    userPlugins: plugins,
    loading,
    error,
    refreshPlugins,
    enablePlugin,
    disablePlugin,
    updatePluginConfig,
  } = usePluginContext();

  return (
    <SettingsPage
      title={t("title")}
      subtitle={t("subtitle")}
      loading={loading}
      loadingLabel={t("loading")}
      error={error ? t("loadError", { error }) : null}
    >
      <SettingsList empty={<p className="text-muted-foreground">{t("empty")}</p>}>
        {plugins.map((plugin) => (
          <PluginListItem
            key={plugin.plugin_name}
            plugin={plugin}
            onEnable={() => enablePlugin(plugin.plugin_name)}
            onDisable={() => disablePlugin(plugin.plugin_name)}
            onConfigChange={(config) => updatePluginConfig(plugin.plugin_name, config)}
            onRefresh={refreshPlugins}
          />
        ))}
      </SettingsList>
    </SettingsPage>
  );
}
