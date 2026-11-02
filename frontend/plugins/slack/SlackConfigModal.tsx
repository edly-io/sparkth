"use client";

import PluginConfigModal from "@/lib/components/settings/ConfigModal";
import type { ConfigModalProps } from "@/lib/settings/slots";
import DocSourcesWidget from "./components/DocSourcesWidget";

// Slack's own controls, by the `widget` hint its backend config fields use.
const CONTROLS = { "doc-sources": DocSourcesWidget };

/** Slack's config modal: the one built from its backend config, plus Slack's own controls. */
export default function SlackConfigModal(props: ConfigModalProps) {
  return <PluginConfigModal {...props} controls={CONTROLS} />;
}
