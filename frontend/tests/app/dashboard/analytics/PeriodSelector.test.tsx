import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
// fireEvent for date inputs: user-event typing into type="date" is unreliable under jsdom.
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import en from "@/messages/en.json";
import { renderWithIntl } from "../../../intl-test-utils";

const nav = vi.hoisted(() => ({ search: "", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => "/dashboard/analytics/logins",
}));

import { PeriodSelector } from "@/app/dashboard/analytics/PeriodSelector";

function intl(ui: React.ReactElement) {
  return (
    <NextIntlClientProvider locale="en" messages={en}>
      {ui}
    </NextIntlClientProvider>
  );
}

beforeEach(() => {
  nav.search = "";
  nav.replace.mockReset();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
});
afterEach(() => vi.useRealTimers());

describe("PeriodSelector", () => {
  it("shows the default period with labelled controls", () => {
    renderWithIntl(<PeriodSelector />);
    expect(screen.getByLabelText("Period")).toHaveValue("30d");
    expect(screen.getByLabelText("Group by")).toHaveValue("day");
  });

  it("writes a preset to the URL", async () => {
    renderWithIntl(<PeriodSelector />);
    await userEvent.selectOptions(screen.getByLabelText("Period"), "7d");
    expect(nav.replace).toHaveBeenCalledWith("/dashboard/analytics/logins?range=7d&bucket=day");
  });

  it("writes the bucket to the URL, keeping the range", async () => {
    nav.search = "range=90d";
    renderWithIntl(<PeriodSelector />);
    await userEvent.selectOptions(screen.getByLabelText("Group by"), "week");
    expect(nav.replace).toHaveBeenCalledWith("/dashboard/analytics/logins?range=90d&bucket=week");
  });

  it("applies a valid custom range", async () => {
    renderWithIntl(<PeriodSelector />);
    await userEvent.selectOptions(screen.getByLabelText("Period"), "custom");
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-07-10" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(nav.replace).toHaveBeenCalledWith(
      "/dashboard/analytics/logins?from=2026-07-01&to=2026-07-10&bucket=day",
    );
  });

  it("blocks an inverted custom range with an inline message", async () => {
    renderWithIntl(<PeriodSelector />);
    await userEvent.selectOptions(screen.getByLabelText("Period"), "custom");
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-10" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-07-01" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/start date must be on or before/i);
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("explains why an invalid link fell back to the default", () => {
    nav.search = "from=2024-01-01&to=2024-01-10";
    renderWithIntl(<PeriodSelector />);
    expect(screen.getByRole("alert")).toHaveTextContent(/within the last 365 days/i);
  });

  it("keeps both of two quick changes made before the URL updates", async () => {
    renderWithIntl(<PeriodSelector />);
    // The mocked router never updates the URL, like a second change landing before the first.
    await userEvent.selectOptions(screen.getByLabelText("Period"), "7d");
    await userEvent.selectOptions(screen.getByLabelText("Group by"), "week");
    expect(nav.replace).toHaveBeenLastCalledWith(
      "/dashboard/analytics/logins?range=7d&bucket=week",
    );
  });

  it("keeps an unapplied custom draft when only the bucket changes", async () => {
    const { rerender } = render(intl(<PeriodSelector />));
    await userEvent.selectOptions(screen.getByLabelText("Period"), "custom");
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-01" } });
    await userEvent.selectOptions(screen.getByLabelText("Group by"), "week");

    nav.search = "range=30d&bucket=week"; // the bucket change lands
    rerender(intl(<PeriodSelector />));

    expect(screen.getByLabelText("Start date")).toHaveValue("2026-07-01");
  });

  it("only offers start dates inside the API's 365-day window", async () => {
    renderWithIntl(<PeriodSelector />);
    await userEvent.selectOptions(screen.getByLabelText("Period"), "custom");
    expect(screen.getByLabelText("Start date")).toHaveAttribute("min", "2025-07-25");
    expect(screen.getByLabelText("Start date")).toHaveAttribute("max", "2026-07-24");
  });
});
