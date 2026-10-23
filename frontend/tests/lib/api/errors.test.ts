import { afterEach, describe, expect, it } from "vitest";

import { rethrowOrWrapConnectionError } from "@/lib/api";
import { setActiveLocale, setActiveMessages } from "@/lib/i18n/active-locale";
import { defaultLocale } from "@/lib/i18n/config";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

describe("rethrowOrWrapConnectionError", () => {
  afterEach(() => {
    setActiveLocale(defaultLocale);
    setActiveMessages(en);
  });

  it("describes a transport failure in the language on screen", () => {
    setActiveLocale("fr");
    setActiveMessages(fr);

    expect(() => rethrowOrWrapConnectionError(new TypeError("Failed to fetch"))).toThrow(
      "Impossible de se connecter au serveur : Failed to fetch",
    );
  });
});
