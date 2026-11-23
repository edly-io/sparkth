import { screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { renderToString } from "react-dom/server";
import { afterEach, describe, it, expect } from "vitest";

import NotFoundPage from "@/app/not-found";
import coreEn from "@/core/i18n/en.json";
import coreEs from "@/core/i18n/es.json";
import { renderWithIntl } from "@/tests/intl";

// The page reads the address the browser is at, so each test sets it before rendering.
afterEach(() => window.history.pushState({}, "", "/"));

describe("NotFoundPage — an address under the dashboard that names no plugin", () => {
  it.each(["/dashboard/nosuchplugin", "/dashboard/nosuchplugin/"])(
    "says no plugin has that name at %s",
    (path) => {
      window.history.pushState({}, "", path);

      renderWithIntl(<NotFoundPage />, coreEn);

      const panel = screen.getByRole("alert");
      expect(panel).toHaveTextContent(coreEn.pluginNotFound.title);
      expect(panel).toHaveTextContent(
        coreEn.pluginNotFound.message.replace("{name}", "nosuchplugin"),
      );
    },
  );

  it("leads back to the dashboard", () => {
    window.history.pushState({}, "", "/dashboard/nosuchplugin/");

    renderWithIntl(<NotFoundPage />, coreEn);

    expect(screen.getByRole("link", { name: coreEn.dashboardLink.back })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("says so in the active language", () => {
    window.history.pushState({}, "", "/dashboard/nosuchplugin/");

    renderWithIntl(<NotFoundPage />, coreEs);

    expect(screen.getByRole("alert")).toHaveTextContent(coreEs.pluginNotFound.title);
  });
});

describe("NotFoundPage — any other address that names no page", () => {
  it.each(["/nosuchpage/", "/dashboard/settings/nosuchpage/", "/dashboard/"])(
    "says the page was not found at %s, without naming a plugin",
    (path) => {
      window.history.pushState({}, "", path);

      renderWithIntl(<NotFoundPage />, coreEn);

      const panel = screen.getByRole("alert");
      expect(panel).toHaveTextContent(coreEn.pageNotFound.title);
      expect(panel).toHaveTextContent(coreEn.pageNotFound.message);
      expect(panel).not.toHaveTextContent(coreEn.pluginNotFound.title);
    },
  );

  it("leads back to the dashboard", () => {
    window.history.pushState({}, "", "/nosuchpage/");

    renderWithIntl(<NotFoundPage />, coreEn);

    expect(screen.getByRole("link", { name: coreEn.dashboardLink.back })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});

describe("NotFoundPage — built ahead of time, before any address is known", () => {
  it("shows nothing", () => {
    window.history.pushState({}, "", "/dashboard/nosuchplugin/");

    const html = renderToString(
      <NextIntlClientProvider locale="en" messages={coreEn}>
        <NotFoundPage />
      </NextIntlClientProvider>,
    );

    expect(html).toBe("");
  });
});
