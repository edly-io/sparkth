import { describe, it, expect, beforeEach } from "vitest";

import { getActiveLocale, setActiveLocale } from "@/lib/i18n/active-locale";
import { defaultLocale } from "@/lib/i18n/config";

describe("active locale", () => {
  beforeEach(() => {
    setActiveLocale(defaultLocale);
  });

  it("starts on the default locale", () => {
    expect(getActiveLocale()).toBe(defaultLocale);
  });

  it("returns whatever was last set", () => {
    setActiveLocale("es");
    expect(getActiveLocale()).toBe("es");
  });
});
