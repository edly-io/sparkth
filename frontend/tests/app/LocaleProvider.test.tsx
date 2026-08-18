import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useLocale } from "next-intl";

import { LocaleProvider } from "@/app/LocaleProvider";
import { LOCALE_COOKIE } from "@/lib/i18n/config";

function LocaleProbe() {
  return <span data-testid="locale">{useLocale()}</span>;
}

describe("LocaleProvider", () => {
  beforeEach(() => {
    document.cookie = `${LOCALE_COOKIE}=; path=/; max-age=0`;
    document.documentElement.lang = "en";
  });

  it("renders nothing until the catalog is loaded", () => {
    const { container } = render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("provides the default locale when no cookie is set", async () => {
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("locale")).toHaveTextContent("en"));
  });

  it("provides the cookie locale and updates the document language", async () => {
    document.cookie = `${LOCALE_COOKIE}=es`;
    render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("locale")).toHaveTextContent("es"));
    expect(document.documentElement.lang).toBe("es");
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
});
