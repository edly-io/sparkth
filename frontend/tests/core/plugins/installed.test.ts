import { afterEach, describe, it, expect } from "vitest";

import { isInstalled } from "@/core/plugins/installed";
import { registerPlugin, unregisterPlugin } from "@/core/plugins/registry";

afterEach(() => {
  unregisterPlugin("exampleplugin");
});

describe("isInstalled", () => {
  it("counts a plugin core registered as installed", () => {
    registerPlugin({
      name: "exampleplugin",
      loadComponent: () => Promise.resolve({ default: () => null }),
    });

    expect(isInstalled("exampleplugin")).toBe(true);
  });

  it("does not count a plugin core never registered", () => {
    expect(isInstalled("exampleplugin")).toBe(false);
  });
});
