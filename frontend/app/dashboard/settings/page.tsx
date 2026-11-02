"use client";

import { useTranslations } from "next-intl";
import { PluginSettingsList } from "@/core/components/settings/PluginSettingsList";
import { SettingsPage } from "@/core/components/settings/SettingsPage";
import { usePluginContext } from "@/core/plugins/context";

export default function PluginsSettings() {
  const t = useTranslations("plugins");
  const { loading, error } = usePluginContext();

  return (
    <SettingsPage
      title={t("title")}
      subtitle={t("subtitle")}
      loading={loading}
      loadingLabel={t("loading")}
      error={error ? t("loadError", { error }) : null}
    >
      <PluginSettingsList />
    </SettingsPage>
  );
}
