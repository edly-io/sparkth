import { describe, it, expect, beforeEach } from "vitest";

import {
  defaultLocale,
  isLocale,
  LOCALE_COOKIE,
  locales,
  readLocaleCookie,
  setLocaleCookie,
} from "@/lib/i18n/config";

function clearLocaleCookie() {
  document.cookie = `${LOCALE_COOKIE}=; path=/; max-age=0`;
}

describe("locale config", () => {
  beforeEach(clearLocaleCookie);

  it("supports en, es and fr with en as the default", () => {
    expect(locales).toEqual(["en", "es", "fr"]);
    expect(defaultLocale).toBe("en");
  });

  it("isLocale accepts supported tags and rejects anything else", () => {
    expect(isLocale("es")).toBe(true);
    expect(isLocale("de")).toBe(false);
    expect(isLocale("")).toBe(false);
  });

  it("readLocaleCookie falls back to the default locale when no cookie is set", () => {
    expect(readLocaleCookie()).toBe(defaultLocale);
  });

  it("readLocaleCookie returns the locale stored in the cookie", () => {
    document.cookie = `${LOCALE_COOKIE}=es`;
    expect(readLocaleCookie()).toBe("es");
  });

  it("readLocaleCookie falls back to the default locale for an unsupported tag", () => {
    document.cookie = `${LOCALE_COOKIE}=de`;
    expect(readLocaleCookie()).toBe(defaultLocale);
  });

  it("readLocaleCookie finds the locale among other cookies", () => {
    document.cookie = "other=value";
    document.cookie = `${LOCALE_COOKIE}=fr`;
    expect(readLocaleCookie()).toBe("fr");
  });

  it("setLocaleCookie round-trips through readLocaleCookie", () => {
    setLocaleCookie("fr");
    expect(readLocaleCookie()).toBe("fr");
  });
});
