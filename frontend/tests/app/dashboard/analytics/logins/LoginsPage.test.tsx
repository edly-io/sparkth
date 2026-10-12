import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";

import en from "@/messages/en.json";
import { renderWithIntl } from "../../../../intl-test-utils";

import { ApiRequestError } from "@/lib/api";

// Auth: a mutable token holder so a test can change identity mid-fetch (stale-response guard).
const auth = vi.hoisted(() => ({ token: "test-token" }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: auth.token }),
}));

// Analytics data access: keep the real types, stub the fetch.
vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return { ...actual, fetchLogins: vi.fn() };
});

const nav = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/analytics/logins",
}));

import { fetchLogins, type LoginsPoint } from "@/lib/analytics";
import LoginsPage from "@/app/dashboard/analytics/logins/LoginsPage";

// rerender must re-wrap, since renderWithIntl returns the bare RTL result.
function intl(ui: React.ReactElement) {
  return (
    <NextIntlClientProvider locale="en" messages={en}>
      {ui}
    </NextIntlClientProvider>
  );
}

// Answers by period: the current period ends on `currentTo`, by default the pinned "today".
function answer(current: LoginsPoint[], previous: LoginsPoint[] = [], currentTo = "2026-07-24") {
  vi.mocked(fetchLogins).mockImplementation(async (_t, { to }) =>
    to === currentTo ? current : previous,
  );
}
const row = (bucket: string, login_count: number, method = "password") => ({
  bucket,
  method,
  login_count,
});

// Pinned so the default 30-day period is 2026-06-25..2026-07-24 and the previous one
// 2026-05-26..2026-06-24. shouldAdvanceTime keeps findByText's polling on the real clock
// while Date stays pinned.
beforeEach(() => {
  vi.clearAllMocks();
  auth.token = "test-token";
  nav.search = "";
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

const card = async (title: string) => (await screen.findByText(title)).parentElement as HTMLElement;
const forbidden = new ApiRequestError({ message: "Permission denied", fieldErrors: {} }, 403);

describe("LoginsPage states", () => {
  it("shows a loading indicator, then the chart and stats", async () => {
    // Distinct counts so the "Total logins" (5) and "Busiest day" (3) tiles differ.
    answer([row("2026-07-23", 3), row("2026-07-22", 2)]);

    renderWithIntl(<LoginsPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(await screen.findByText("5")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /^Logins,/ })).toBeInTheDocument();
  });

  it("formats the busiest day as a UTC date even when the browser is west of UTC", async () => {
    // 2026-07-23 00:00 UTC is still 2026-07-22 in America/Los_Angeles, so the label slips a
    // day unless the page formats in UTC.
    answer([row("2026-07-23", 3)]);
    render(
      <NextIntlClientProvider locale="en" messages={en} timeZone="America/Los_Angeles">
        <LoginsPage />
      </NextIntlClientProvider>,
    );
    const busiestCard = await card("Busiest day");
    expect(within(busiestCard).getByText(/^Jul 23, 2026 ·/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no logins", async () => {
    answer([]);
    renderWithIntl(<LoginsPage />);
    expect(await screen.findByText(/no logins in this period/i)).toBeInTheDocument();
  });

  it("shows the empty state when only the previous period had logins", async () => {
    answer([], [row("2026-06-20", 4)]);
    renderWithIntl(<LoginsPage />);
    expect(await screen.findByText(/no logins in this period/i)).toBeInTheDocument();
    expect(screen.queryByText("Total logins")).not.toBeInTheDocument();
  });

  it("shows the empty state when every row falls outside the period", async () => {
    answer([row("2000-01-01", 5)]);
    renderWithIntl(<LoginsPage />);
    expect(await screen.findByText(/no logins in this period/i)).toBeInTheDocument();
    expect(screen.queryByText("Total logins")).not.toBeInTheDocument();
    expect(screen.queryByText("Busiest day")).not.toBeInTheDocument();
  });

  it("labels the window as UTC in the subheading so dates are not misread across timezones", () => {
    answer([]);
    renderWithIntl(<LoginsPage />);
    expect(screen.getByText(/\(UTC\)/)).toBeInTheDocument();
  });

  it("shows the 403 view when access is revoked, without disclosing permission details", async () => {
    vi.mocked(fetchLogins).mockRejectedValue(forbidden);

    renderWithIntl(<LoginsPage />);

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/analytics\.read/i)).not.toBeInTheDocument();
  });

  it("shows the 403 view when only the previous-period request is forbidden", async () => {
    vi.mocked(fetchLogins).mockImplementation(async (_t, { to }) => {
      if (to === "2026-07-24") return [row("2026-07-23", 3)];
      throw forbidden;
    });

    renderWithIntl(<LoginsPage />);

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
  });

  it("shows a generic error on other failures", async () => {
    vi.mocked(fetchLogins).mockRejectedValue(
      new ApiRequestError({ message: "boom", fieldErrors: {} }, 500),
    );

    renderWithIntl(<LoginsPage />);

    expect(
      await screen.findByText(/couldn't load|could not load|failed to load/i),
    ).toBeInTheDocument();
  });

  it("re-fetches when the error state's retry button is pressed", async () => {
    answer([row("2026-07-23", 3), row("2026-07-22", 2)]);
    vi.mocked(fetchLogins).mockRejectedValueOnce(
      new ApiRequestError({ message: "boom", fieldErrors: {} }, 500),
    );

    renderWithIntl(<LoginsPage />);

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));

    expect(await screen.findByText("Total logins")).toBeInTheDocument();
    expect(fetchLogins).toHaveBeenCalledTimes(4); // two periods, twice
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });
});

describe("LoginsPage comparison and methods", () => {
  it("fetches the period and the previous period of equal length", async () => {
    nav.search = "from=2026-07-01&to=2026-07-10";
    answer([]);
    renderWithIntl(<LoginsPage />);
    await screen.findByText(/no logins in this period/i);
    expect(fetchLogins).toHaveBeenCalledWith("test-token", {
      from: "2026-07-01",
      to: "2026-07-10",
    });
    expect(fetchLogins).toHaveBeenCalledWith("test-token", {
      from: "2026-06-21",
      to: "2026-06-30",
    });
  });

  it("adds every sign-in method into the trend", async () => {
    answer([row("2026-07-23", 2), row("2026-07-23", 3, "google")]);
    renderWithIntl(<LoginsPage />);
    expect(within(await card("Total logins")).getByText("5")).toBeInTheDocument();
  });

  it("compares the total with the previous period", async () => {
    answer([row("2026-07-23", 6)], [row("2026-06-20", 4)]);
    renderWithIntl(<LoginsPage />);
    expect(
      within(await card("Total logins")).getByText("+50% vs previous period"),
    ).toBeInTheDocument();
  });

  it("says when the previous period had no logins", async () => {
    answer([row("2026-07-23", 6)]);
    renderWithIntl(<LoginsPage />);
    expect(
      within(await card("Total logins")).getByText("No logins in the previous period"),
    ).toBeInTheDocument();
  });

  it("compares the busiest bucket with the previous period's", async () => {
    // Equal totals (4 vs 4), so only the busiest bucket (3 vs 2) shows a change.
    answer(
      [row("2026-07-23", 3), row("2026-07-22", 1)],
      [row("2026-06-20", 2), row("2026-06-21", 2)],
    );
    renderWithIntl(<LoginsPage />);
    expect(
      within(await card("Busiest day")).getByText(/\+50% vs previous period/),
    ).toBeInTheDocument();
  });

  it("draws the previous period as the comparison", async () => {
    // 2026-06-23 is day 29 of the previous period, so it lines up with 2026-07-23.
    answer([row("2026-07-23", 3)], [row("2026-06-23", 7)]);
    renderWithIntl(<LoginsPage />);
    const table = await screen.findByRole("table", { name: /^Logins,/ });
    expect(
      within(table).getByRole("columnheader", { name: "Previous period" }),
    ).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 3 7" })).toBeInTheDocument();
  });

  it("lines up the previous period's last bucket with the current one when it has more", async () => {
    // The previous period, 2026-01-29..2026-02-28, spans January and February; March is
    // compared with February.
    nav.search = "from=2026-03-01&to=2026-03-31&bucket=month";
    answer([row("2026-03-10", 5)], [row("2026-01-30", 9), row("2026-02-10", 4)], "2026-03-31");
    renderWithIntl(<LoginsPage />);
    const table = await screen.findByRole("table", { name: /^Logins,/ });
    expect(within(table).getByRole("row", { name: "Mar 2026 5 4" })).toBeInTheDocument();
  });

  it("breaks logins down by sign-in method with counts and shares", async () => {
    answer([row("2026-07-23", 3), row("2026-07-22", 1, "google")]);
    renderWithIntl(<LoginsPage />);
    const table = await screen.findByRole("table", { name: /by sign-in method/i });
    expect(
      within(table).getByRole("row", { name: "Email and password 3 (75%)" }),
    ).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "Google 1 (25%)" })).toBeInTheDocument();
  });

  it("shows an unknown sign-in method by its raw name", async () => {
    answer([row("2026-07-23", 1, "saml")]);
    renderWithIntl(<LoginsPage />);
    const table = await screen.findByRole("table", { name: /by sign-in method/i });
    expect(within(table).getByRole("rowheader", { name: "saml" })).toBeInTheDocument();
  });
});

describe("LoginsPage stale-response guard", () => {
  function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((r) => {
      resolve = r;
    });
    return { promise, resolve };
  }

  it("ignores an earlier request that resolves after a newer one when the token changes mid-fetch", async () => {
    const first = deferred<LoginsPoint[]>();
    const second = deferred<LoginsPoint[]>();
    vi.mocked(fetchLogins).mockImplementation((token, { to }) => {
      if (to !== "2026-07-24") return Promise.resolve([]);
      return token === "token-A" ? first.promise : second.promise;
    });

    auth.token = "token-A";
    const { rerender } = renderWithIntl(<LoginsPage />); // token-A: pending

    auth.token = "token-B";
    rerender(intl(<LoginsPage />)); // token changed → refetch with token-B, pending

    // The newer request (B) resolves first and is shown…
    await act(async () => {
      second.resolve([row("2026-07-24", 2)]);
    });
    const totalCard = await card("Total logins");
    expect(within(totalCard).getByText("2")).toBeInTheDocument();

    // …then the stale request (A) resolves last and must NOT overwrite it.
    await act(async () => {
      first.resolve([row("2026-07-24", 9)]);
    });
    expect(within(totalCard).getByText("2")).toBeInTheDocument();
    expect(screen.queryByText("9")).not.toBeInTheDocument();
  });
});

describe("LoginsPage period", () => {
  it("re-buckets without refetching when only the bucket changes", async () => {
    nav.search = "range=30d&bucket=week";
    answer([row("2026-07-21", 3)]);
    const { rerender } = render(intl(<LoginsPage />));
    expect(await screen.findByText("Busiest week")).toBeInTheDocument();

    nav.search = "range=30d&bucket=month";
    rerender(intl(<LoginsPage />));
    const busiestCard = await card("Busiest month");
    expect(within(busiestCard).getByText(/^Jul 2026 ·/)).toBeInTheDocument();
    expect(fetchLogins).toHaveBeenCalledTimes(2); // the period and the previous one, once
  });

  it("refetches when the end date changes", async () => {
    nav.search = "from=2026-07-01&to=2026-07-10";
    answer([]);
    const { rerender } = render(intl(<LoginsPage />));
    await screen.findByText(/no logins in this period/i);

    nav.search = "from=2026-07-01&to=2026-07-15";
    rerender(intl(<LoginsPage />));
    await waitFor(() => expect(fetchLogins).toHaveBeenCalledTimes(4));
  });

  it("labels a month bucket by month", async () => {
    nav.search = "range=30d&bucket=month";
    answer([row("2026-07-21", 3)]);
    renderWithIntl(<LoginsPage />);
    expect(within(await card("Busiest month")).getByText(/^Jul 2026 ·/)).toBeInTheDocument();
  });

  it("labels a week bucket by its Monday", async () => {
    nav.search = "range=30d&bucket=week";
    answer([row("2026-07-21", 3)]);
    renderWithIntl(<LoginsPage />);
    expect(
      within(await card("Busiest week")).getByText(/^Week of Jul 20, 2026 ·/),
    ).toBeInTheDocument();
  });
});
