import { describe, it, expect, vi, afterEach } from "vitest";

import { loadMessages } from "@/lib/i18n/messages";
import { locales } from "@/lib/i18n/config";
import { getAllPlugins, registerPlugin, unregisterPlugin } from "@/lib/plugins";
import coreEn from "@/messages/en.json";
import coreEs from "@/messages/es.json";
import coreFr from "@/messages/fr.json";

const CORE_CATALOGS = { en: coreEn, es: coreEs, fr: coreFr } as const;

describe("loadMessages", () => {
  it("merges every registered plugin catalog into the core catalog", async () => {
    const messages = await loadMessages("es");

    expect(messages).toHaveProperty("home");
    expect(messages).toHaveProperty("chat");
  });

  it("merges plugin catalogs for the default locale too", async () => {
    const messages = await loadMessages("en");

    expect(messages).toHaveProperty("chat");
  });
});

describe("plugin catalog containment", () => {
  it("keeps core catalogs free of plugin namespaces", () => {
    const pluginNames = getAllPlugins().map((plugin) => plugin.name);
    for (const catalog of Object.values(CORE_CATALOGS)) {
      for (const name of pluginNames) {
        expect(Object.keys(catalog)).not.toContain(name);
      }
    }
  });

  it("scopes every plugin catalog to the plugin's own namespace, in every locale", async () => {
    for (const plugin of getAllPlugins()) {
      if (!plugin.loadMessages) continue;
      for (const locale of locales) {
        const catalog = await plugin.loadMessages(locale);
        expect(Object.keys(catalog), `${plugin.name}/${locale}`).toEqual([plugin.name]);
      }
    }
  });
});

describe("plugin catalog failure", () => {
  afterEach(() => {
    unregisterPlugin("broken");
    vi.restoreAllMocks();
  });

  it("falls back to the plugin's English catalog and logs when a locale fails to load", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    registerPlugin({
      name: "broken",
      loadComponent: () => Promise.reject(new Error("not rendered here")),
      loadMessages: (locale) =>
        locale === "en"
          ? Promise.resolve({ broken: { label: "english fallback" } })
          : Promise.reject(new Error("chunk load failed")),
    });

    const messages = await loadMessages("es");

    expect(messages).toHaveProperty("broken", { label: "english fallback" });
    expect(messages).toHaveProperty("home");
    expect(consoleError).toHaveBeenCalled();
  });

  it("still resolves the core catalog when a plugin has no loadable catalog at all", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    registerPlugin({
      name: "broken",
      loadComponent: () => Promise.reject(new Error("not rendered here")),
      loadMessages: () => Promise.reject(new Error("chunk load failed")),
    });

    const messages = await loadMessages("en");

    expect(messages).toHaveProperty("home");
    expect(messages).not.toHaveProperty("broken");
    expect(consoleError).toHaveBeenCalled();
  });
});
