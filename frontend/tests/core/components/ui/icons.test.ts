import { describe, it, expect, vi, afterEach } from "vitest";

import { resolvePluginIcon } from "@/core/components/ui/icons";
import { PLUGIN_ICONS } from "@/lib/icons/slots";

function ExampleIcon() {
  return null;
}

function OtherIcon() {
  return null;
}

describe("resolvePluginIcon", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    PLUGIN_ICONS.clear();
  });

  it("resolves the icon a plugin set, by its name", () => {
    PLUGIN_ICONS.set("example", [{ name: "example-brand", component: ExampleIcon }]);

    expect(resolvePluginIcon("example", "example-brand")).toBe(ExampleIcon);
  });

  it("resolves a name from the declaring plugin's own icons when another plugin uses it too", () => {
    PLUGIN_ICONS.set("example", [{ name: "plus", component: ExampleIcon }]);
    PLUGIN_ICONS.set("other", [{ name: "plus", component: OtherIcon }]);

    expect(resolvePluginIcon("example", "plus")).toBe(ExampleIcon);
    expect(resolvePluginIcon("other", "plus")).toBe(OtherIcon);
  });

  it("does not resolve a name only another plugin set", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    PLUGIN_ICONS.set("other", [{ name: "plus", component: OtherIcon }]);

    expect(resolvePluginIcon("example", "plus")).toBeUndefined();
  });

  it("returns undefined for unknown or missing names", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(resolvePluginIcon("example", "no-such-icon")).toBeUndefined();
    expect(resolvePluginIcon("example", null)).toBeUndefined();
    expect(resolvePluginIcon("example", undefined)).toBeUndefined();
  });

  it("warns about a name its plugin did not set outside production so the gap is visible", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    resolvePluginIcon("example", "no-such-icon");
    expect(warn).toHaveBeenCalledOnce();
    expect(warn.mock.calls[0][0]).toContain("no-such-icon");
    expect(warn.mock.calls[0][0]).toContain("example");
  });
});
