import { fireEvent, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import type { PluginState } from "@/lib/plugins/types";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";
import { renderWithIntl } from "@/lib/testing/intl";
import { COURSE_DESIGN_PLUGIN_NAME } from "@/plugins/course_design/src/constants";
import "@/plugins/course_design/src/slots/settings";

const COURSE_DESIGN: PluginState = {
  plugin_name: COURSE_DESIGN_PLUGIN_NAME,
  enabled: true,
  system_enabled: true,
  config: {},
  config_schema: {},
  is_core: false,
  display: { display_name: "Course design", description: "Design courses" },
  sidebar: null,
  has_frontend: false,
  secrets_set: [],
  masked_secrets: {},
};

describe("course design's settings row", () => {
  it("lets the user switch course design off", () => {
    const ListItem = SETTINGS_ITEMS.get(COURSE_DESIGN_PLUGIN_NAME)?.listItem;
    if (!ListItem) throw new Error("course design registered no settings row");
    const onDisable = vi.fn(async () => {});

    renderWithIntl(
      <ListItem
        plugin={COURSE_DESIGN}
        onEnable={vi.fn(async () => {})}
        onDisable={onDisable}
        onConfigure={undefined}
        configuring={false}
      />,
    );
    fireEvent.click(screen.getByRole("switch", { name: "Turn Course design on or off" }));

    expect(onDisable).toHaveBeenCalled();
  });

  it("offers no config modal", () => {
    expect(SETTINGS_ITEMS.get(COURSE_DESIGN_PLUGIN_NAME)?.loadConfigModal).toBeUndefined();
  });
});
