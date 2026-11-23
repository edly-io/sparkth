import { screen } from "@testing-library/react";
import { afterEach, describe, it, expect } from "vitest";

import NotFoundPage from "@/app/not-found";
import coreEn from "@/core/i18n/en.json";
import coreEs from "@/core/i18n/es.json";
import { renderWithIntl } from "@/tests/intl";

// The page reads the address the browser is at, so a test sets it before rendering.
function openAt(path: string): void {
  window.history.pushState({}, "", path);
}

afterEach(() => openAt("/"));

describe("NotFoundPage — an address under the dashboard that names no plugin", () => {
  it.each(["/dashboard/nosuchplugin", "/dashboard/nosuchplugin/"])(
    "says no plugin has that name at %s",
    (path) => {
      openAt(path);

      renderWithIntl(<NotFoundPage />, coreEn);

      const panel = screen.getByRole("alert");
      expect(panel).toHaveTextContent(coreEn.pluginNotFound.title);
      expect(panel).toHaveTextContent(
        coreEn.pluginNotFound.message.replace("{name}", "nosuchplugin"),
      );
    },
  );

  it("leads back to the dashboard", () => {
    openAt("/dashboard/nosuchplugin/");

    renderWithIntl(<NotFoundPage />, coreEn);

    expect(screen.getByRole("link", { name: coreEn.dashboardLink.back })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("says so in the active language", () => {
    openAt("/dashboard/nosuchplugin/");

    renderWithIntl(<NotFoundPage />, coreEs);

    expect(screen.getByRole("alert")).toHaveTextContent(coreEs.pluginNotFound.title);
  });
});

describe("NotFoundPage — any other address that names no page", () => {
  it.each(["/nosuchpage/", "/dashboard/settings/nosuchpage/", "/dashboard/"])(
    "says the page was not found at %s, without naming a plugin",
    (path) => {
      openAt(path);

      renderWithIntl(<NotFoundPage />, coreEn);

      const panel = screen.getByRole("alert");
      expect(panel).toHaveTextContent(coreEn.pageNotFound.title);
      expect(panel).toHaveTextContent(coreEn.pageNotFound.message);
      expect(panel).not.toHaveTextContent(coreEn.pluginNotFound.title);
    },
  );

  it("leads back to the dashboard", () => {
    openAt("/nosuchpage/");

    renderWithIntl(<NotFoundPage />, coreEn);

    expect(screen.getByRole("link", { name: coreEn.dashboardLink.back })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});
