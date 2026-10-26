import { describe, it, expect } from "vitest";

import { resolvePluginIcon } from "@/core/plugins/icons";
import { registerPluginIcon } from "@/lib/plugins/icons";

function ExampleBrandIcon(): null {
  return null;
}

describe("registerPluginIcon", () => {
  it("registers an icon that core resolves by name", () => {
    registerPluginIcon("example-brand", ExampleBrandIcon);

    expect(resolvePluginIcon("example-brand")).toBe(ExampleBrandIcon);
  });
});
