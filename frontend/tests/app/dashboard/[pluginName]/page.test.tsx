import { afterEach, describe, it, expect } from "vitest";

import { generateStaticParams } from "@/app/dashboard/[pluginName]/page";
import { registerPlugin, unregisterPlugin } from "@/core/plugins/registry";

afterEach(() => {
  unregisterPlugin("exampleplugin");
});

describe("generateStaticParams", () => {
  it("builds a page for every plugin core registered", () => {
    registerPlugin({
      name: "exampleplugin",
      loadComponent: () => Promise.resolve({ default: () => null }),
    });

    expect(generateStaticParams()).toContainEqual({ pluginName: "exampleplugin" });
  });
});
