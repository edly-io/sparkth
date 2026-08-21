import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useLocale } from "next-intl";

import { LocaleProvider } from "@/app/LocaleProvider";
import { getActiveLocale, setActiveLocale } from "@/lib/i18n/active-locale";
import { defaultLocale, LOCALE_COOKIE, type Locale } from "@/lib/i18n/config";

// Lets the failure test make the catalog import reject while every other test
// exercises the real loader.
const failLoad = vi.hoisted(() => ({ value: false }));
vi.mock("@/lib/i18n/messages", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/i18n/messages")>();
  return {
    ...actual,
    loadMessages: (locale: Locale) =>
      failLoad.value ? Promise.reject(new Error("chunk load failed")) : actual.loadMessages(locale),
  };
});

function LocaleProbe() {
  return <span data-testid="locale">{useLocale()}</span>;
}

describe("LocaleProvider", () => {
  beforeEach(() => {
    failLoad.value = false;
    document.cookie = `${LOCALE_COOKIE}=; path=/; max-age=0`;
    document.documentElement.lang = "en";
    setActiveLocale(defaultLocale);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders immediately with the default locale, before any catalog import resolves", () => {
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("locale")).toHaveTextContent("en");
  });

  it("keeps the default locale when no cookie is set", async () => {
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("locale")).toHaveTextContent("en"));
  });

  it("swaps to the cookie locale and updates the document language", async () => {
    document.cookie = `${LOCALE_COOKIE}=es`;
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("locale")).toHaveTextContent("es"));
    expect(document.documentElement.lang).toBe("es");
    expect(getActiveLocale()).toBe("es");
  });

  it("falls back to the default locale for an unsupported cookie value", async () => {
    document.cookie = `${LOCALE_COOKIE}=de`;
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("locale")).toHaveTextContent("en"));
    expect(document.documentElement.lang).toBe("en");
  });

  it("stays on the default catalog and logs when the locale catalog fails to load", async () => {
    failLoad.value = true;
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    document.cookie = `${LOCALE_COOKIE}=es`;

    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );

    await waitFor(() => expect(consoleError).toHaveBeenCalled());
    expect(screen.getByTestId("locale")).toHaveTextContent("en");
    expect(document.documentElement.lang).toBe("en");
    // The cookie still names "es", but what the UI renders is English; API calls
    // read the active locale, so backend responses stay in the rendered language.
    expect(getActiveLocale()).toBe("en");
  });
});
