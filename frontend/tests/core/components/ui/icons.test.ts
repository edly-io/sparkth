import { describe, it, expect, vi, afterEach } from "vitest";

import { resolvePluginIcon } from "@/core/components/ui/icons";
import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { setNamedSlotItems } from "@/lib/slots";

function ExampleBrandIcon() {
  return null;
}

describe("resolvePluginIcon", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setNamedSlotItems(PLUGIN_ICONS, "example", []);
  });

  it("resolves the icon a plugin set, by its name", () => {
    setNamedSlotItems(PLUGIN_ICONS, "example", [
      { name: "example-brand", component: ExampleBrandIcon },
    ]);

    expect(resolvePluginIcon("example-brand")).toBe(ExampleBrandIcon);
  });

  it("returns undefined for unknown or missing names", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(resolvePluginIcon("no-such-icon")).toBeUndefined();
    expect(resolvePluginIcon(null)).toBeUndefined();
    expect(resolvePluginIcon(undefined)).toBeUndefined();
  });

  it("warns about a name no plugin set outside production so the gap is visible", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    resolvePluginIcon("no-such-icon");
    expect(warn).toHaveBeenCalledOnce();
    expect(warn.mock.calls[0][0]).toContain("no-such-icon");
  });
});
