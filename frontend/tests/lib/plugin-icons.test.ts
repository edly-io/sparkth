import { describe, it, expect, vi, afterEach } from "vitest";

import { registerPluginIcon, resolvePluginIcon } from "@/lib/plugins/icons";

describe("resolvePluginIcon", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resolves built-in lucide icon names", () => {
    expect(resolvePluginIcon("plus")).toBeDefined();
  });

  it("returns undefined for unknown or missing names", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(resolvePluginIcon("no-such-icon")).toBeUndefined();
    expect(resolvePluginIcon(null)).toBeUndefined();
    expect(resolvePluginIcon(undefined)).toBeUndefined();
  });

  it("warns about an unregistered name outside production so the gap is visible", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    resolvePluginIcon("no-such-icon");
    expect(warn).toHaveBeenCalledOnce();
    expect(warn.mock.calls[0][0]).toContain("no-such-icon");
  });

  it("resolves custom icons registered by plugins", () => {
    const Custom = () => null;
    registerPluginIcon("custom-brand", Custom);
    expect(resolvePluginIcon("custom-brand")).toBe(Custom);
  });
});
