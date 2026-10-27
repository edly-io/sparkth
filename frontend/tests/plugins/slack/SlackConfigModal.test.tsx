import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import SlackConfigModal from "@/plugins/slack/SlackConfigModal";
import type { UserPluginState } from "@/core/plugins/types";

vi.mock("@/lib/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/slack", () => ({
  fetchRagSources: vi.fn(async () => ({ sources: ["handbook.pdf"] })),
}));

const SLACK: UserPluginState = {
  plugin_name: "slack",
  enabled: true,
  config: {},
  config_schema: {
    type: "object",
    properties: {
      allowed_sources: { title: "Allowed Sources", type: "array", widget: "doc-sources" },
    },
  },
  is_core: false,
  display: null,
  sidebar: null,
  has_frontend: true,
};

describe("SlackConfigModal", () => {
  it("renders the documentation sources control for the field that hints it", async () => {
    render(
      <SlackConfigModal
        plugin={SLACK}
        open
        onOpenChange={vi.fn()}
        onSave={vi.fn(async () => {})}
        onRefresh={vi.fn()}
      />,
    );

    expect(await screen.findByRole("checkbox", { name: "handbook.pdf" })).toBeDefined();
  });
});
