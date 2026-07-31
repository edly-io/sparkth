import { describe, it, expect } from "vitest";

import { registerPluginIcon, resolvePluginIcon } from "@/lib/plugins/icons";

describe("resolvePluginIcon", () => {
  it("resolves built-in lucide icon names", () => {
    expect(resolvePluginIcon("plus")).toBeDefined();
  });

  it("returns undefined for unknown or missing names", () => {
    expect(resolvePluginIcon("no-such-icon")).toBeUndefined();
    expect(resolvePluginIcon(null)).toBeUndefined();
    expect(resolvePluginIcon(undefined)).toBeUndefined();
  });

  it("resolves custom icons registered by plugins", () => {
    const Custom = () => null;
    registerPluginIcon("custom-brand", Custom);
    expect(resolvePluginIcon("custom-brand")).toBe(Custom);
  });
});
