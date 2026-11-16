import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";

import en from "@/core/i18n/catalogs/en";
import es from "@/core/i18n/catalogs/es";
import fr from "@/core/i18n/catalogs/fr";
import { locales, type Locale } from "@/lib/i18n/config";

const merged: Record<Locale, Record<string, unknown>> = { en, es, fr };
const coreDir = path.resolve(__dirname, "../../../core");

/** Every core feature's catalog file for the locale, found on disk. */
function featureCatalogs(locale: Locale): Record<string, unknown>[] {
  const found: Record<string, unknown>[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (path.basename(dir) === "i18n" && entry.name === `${locale}.json`) {
        found.push(JSON.parse(readFileSync(full, "utf8")));
      }
    }
  };
  walk(coreDir);
  return found;
}

describe("core catalogs", () => {
  it.each(locales)("merges every core feature's %s catalog", (locale) => {
    const files = featureCatalogs(locale);

    expect(files.length).toBeGreaterThan(0);
    expect(merged[locale]).toEqual(Object.assign({}, ...files));
  });

  it("gives each namespace to exactly one feature", () => {
    const namespaces = featureCatalogs("en").flatMap((catalog) => Object.keys(catalog));

    expect(new Set(namespaces).size).toBe(namespaces.length);
  });

  it.each(locales)("carries the same namespaces in %s as in English", (locale) => {
    expect(Object.keys(merged[locale]).sort()).toEqual(Object.keys(en).sort());
  });
});
