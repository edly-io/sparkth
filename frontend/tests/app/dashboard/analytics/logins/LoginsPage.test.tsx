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
  return { ...actual, fetchLoginActivity: vi.fn() };
});

const nav = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/analytics/logins",
}));

import { fetchLoginActivity, type LoginActivityPoint } from "@/lib/analytics";
import LoginsPage from "@/app/dashboard/analytics/logins/LoginsPage";

// rerender must re-wrap, since renderWithIntl returns the bare RTL result.
function intl(ui: React.ReactElement) {
  return (
    <NextIntlClientProvider locale="en" messages={en}>
      {ui}
    </NextIntlClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  auth.token = "test-token";
  nav.search = "";
});

describe("LoginsPage states", () => {
  // The page windows to the trailing 30 days from the real clock, so the fixture days below
  // drift out of that window as time passes and the derived totals change under the test.
  // Pinning the clock is what makes those days mean something fixed. Same shape as the
  // window-consistency block below: shouldAdvanceTime keeps findByText's polling on the real
  // clock while Date stays pinned.
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a loading indicator, then the chart and stats", async () => {
    // Two points with distinct counts so the "Total logins" (5) and "Busiest
    // day" (3) stat tiles render different text — a single point would make
    // both tiles show the same value and collide on the `findByText("5")` query.
    vi.mocked(fetchLoginActivity).mockResolvedValue([
      { day: "2026-07-23", login_count: 3 },
      { day: "2026-07-22", login_count: 2 },
    ]);

    const { container } = renderWithIntl(<LoginsPage />);

    // loading first
    expect(screen.getByText(/loading/i)).toBeInTheDocument();

    // then content: total logins stat + a chart
    expect(await screen.findByText("5")).toBeInTheDocument();
    await waitFor(() => expect(container.querySelector("svg[role='img']")).toBeInTheDocument());
  });

  it("formats the busiest day as a UTC date even when the browser is west of UTC", async () => {
    // The real LocaleProvider passes the browser's zone to next-intl; 2026-07-23 00:00 UTC is
    // still 2026-07-22 in America/Los_Angeles, so the label slips a day unless formatDay pins UTC.
    vi.mocked(fetchLoginActivity).mockResolvedValue([{ day: "2026-07-23", login_count: 3 }]);
    render(
      <NextIntlClientProvider locale="en" messages={en} timeZone="America/Los_Angeles">
        <LoginsPage />
      </NextIntlClientProvider>,
    );
    const busiestCard = (await screen.findByText("Busiest day")).parentElement as HTMLElement;
    expect(within(busiestCard).getByText("Jul 23, 2026")).toBeInTheDocument();
  });

  it("shows an empty state when there are no logins", async () => {
    vi.mocked(fetchLoginActivity).mockResolvedValue([]);

    renderWithIntl(<LoginsPage />);

    expect(await screen.findByText(/no logins in this period/i)).toBeInTheDocument();
  });

  it("labels the window as UTC in the subheading so dates are not misread across timezones", () => {
    vi.mocked(fetchLoginActivity).mockResolvedValue([]);

    renderWithIntl(<LoginsPage />);

    // Dates are UTC-bucketed server-side (see lib/analytics reads); the subheading must say
    // so, or a user in another timezone reads the last bar as "today" and it disagrees.
    expect(screen.getByText(/\(UTC\)/)).toBeInTheDocument();
  });

  it("shows the 403 view when access is revoked, without disclosing permission details", async () => {
    vi.mocked(fetchLoginActivity).mockRejectedValue(
      new ApiRequestError({ message: "Permission denied", fieldErrors: {} }, 403),
    );

    renderWithIntl(<LoginsPage />);

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    // No permission name is disclosed anywhere.
    expect(screen.queryByText(/analytics\.read/i)).not.toBeInTheDocument();
  });

  it("shows a generic error on other failures", async () => {
    vi.mocked(fetchLoginActivity).mockRejectedValue(
      new ApiRequestError({ message: "boom", fieldErrors: {} }, 500),
    );

    renderWithIntl(<LoginsPage />);

    expect(
      await screen.findByText(/couldn't load|could not load|failed to load/i),
    ).toBeInTheDocument();
  });

  it("re-fetches when the error state's retry button is pressed", async () => {
    vi.mocked(fetchLoginActivity)
      .mockRejectedValueOnce(new ApiRequestError({ message: "boom", fieldErrors: {} }, 500))
      .mockResolvedValueOnce([
        { day: "2026-07-23", login_count: 3 },
        { day: "2026-07-22", login_count: 2 },
      ]);

    renderWithIntl(<LoginsPage />);

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));

    expect(await screen.findByText("Total logins")).toBeInTheDocument();
    expect(fetchLoginActivity).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });
});

describe("LoginsPage stat/chart window consistency", () => {
  beforeEach(() => {
    // shouldAdvanceTime keeps waitFor/findByText's internal polling ticking on the real
    // clock while Date/new Date() stays pinned to the value set via setSystemTime.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("derives the stat tiles from the same 30-day window as the chart, not the raw response", async () => {
    // The read API's window floor is inclusive (`>= now - days`), so it can return a login
    // dated exactly `today - DAYS` (2026-06-24, 30 days before 2026-07-24). But the 30-slot
    // chart built by buildSeries only spans [today-29 .. today] (oldest slot 2026-06-25),
    // so that boundary day has no bar. Only 2026-07-23 is inside the chart's window.
    vi.mocked(fetchLoginActivity).mockResolvedValue([
      { day: "2026-06-24", login_count: 5 },
      { day: "2026-07-23", login_count: 2 },
    ]);

    renderWithIntl(<LoginsPage />);

    const totalCard = (await screen.findByText("Total logins")).parentElement as HTMLElement;
    // Windowed total is 2 (only 2026-07-23), not 7 (5 + 2 from the raw response).
    expect(within(totalCard).getByText("2")).toBeInTheDocument();

    const busiestCard = screen.getByText("Busiest day").parentElement as HTMLElement;
    // Busiest in-window day is 2026-07-23 (count 2), not the out-of-window 2026-06-24 (count 5).
    expect(within(busiestCard).getByText("2")).toBeInTheDocument();
    expect(within(busiestCard).getByText("Jul 23, 2026")).toBeInTheDocument();

    expect(screen.queryByText("Jun 24, 2026")).not.toBeInTheDocument();
    expect(screen.queryByText("7")).not.toBeInTheDocument();
  });
});

describe("LoginsPage empty-window composition", () => {
  it("shows the empty state when the API returns rows but all fall outside the chart window", async () => {
    vi.mocked(fetchLoginActivity).mockResolvedValue([{ day: "2000-01-01", login_count: 5 }]);

    renderWithIntl(<LoginsPage />);

    expect(await screen.findByText(/no logins in this period/i)).toBeInTheDocument();
    expect(screen.queryByText("Total logins")).not.toBeInTheDocument();
    expect(screen.queryByText("Busiest day")).not.toBeInTheDocument();
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
    const today = new Date().toISOString().slice(0, 10); // always in-window
    const first = deferred<LoginActivityPoint[]>();
    const second = deferred<LoginActivityPoint[]>();
    vi.mocked(fetchLoginActivity)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    auth.token = "token-A";
    const { rerender } = renderWithIntl(<LoginsPage />); // fetches with token-A (first, pending)

    auth.token = "token-B";
    rerender(intl(<LoginsPage />)); // token changed → refetch with token-B (second, pending)

    // The newer request (B) resolves first and is shown…
    await act(async () => {
      second.resolve([{ day: today, login_count: 2 }]);
    });
    const totalCard = (await screen.findByText("Total logins")).parentElement as HTMLElement;
    expect(within(totalCard).getByText("2")).toBeInTheDocument();

    // …then the stale request (A) resolves last and must NOT overwrite it.
    await act(async () => {
      first.resolve([{ day: today, login_count: 9 }]);
    });
    expect(within(totalCard).getByText("2")).toBeInTheDocument();
    expect(screen.queryByText("9")).not.toBeInTheDocument();
  });
});

describe("LoginsPage period", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("fetches enough days to cover a custom range and totals only that range", async () => {
    nav.search = "from=2026-07-01&to=2026-07-10";
    vi.mocked(fetchLoginActivity).mockResolvedValue([
      { day: "2026-07-20", login_count: 9 }, // after `to`: excluded
      { day: "2026-07-05", login_count: 2 },
    ]);
    renderWithIntl(<LoginsPage />);
    const totalCard = (await screen.findByText("Total logins")).parentElement as HTMLElement;
    expect(within(totalCard).getByText("2")).toBeInTheDocument();
    expect(fetchLoginActivity).toHaveBeenCalledWith("test-token", { days: 24 }); // 07-01..07-24
  });

  it("re-buckets without refetching when only the bucket changes", async () => {
    nav.search = "range=30d&bucket=week";
    vi.mocked(fetchLoginActivity).mockResolvedValue([{ day: "2026-07-21", login_count: 3 }]);
    const { rerender } = render(intl(<LoginsPage />));
    expect(await screen.findByText("Busiest week")).toBeInTheDocument();

    nav.search = "range=30d&bucket=month";
    rerender(intl(<LoginsPage />));
    const busiestCard = (await screen.findByText("Busiest month")).parentElement as HTMLElement;
    expect(within(busiestCard).getByText("Jul 2026")).toBeInTheDocument();
    expect(fetchLoginActivity).toHaveBeenCalledTimes(1);
  });

  it("re-buckets without refetching when only the end date changes", async () => {
    nav.search = "from=2026-07-01&to=2026-07-10";
    vi.mocked(fetchLoginActivity).mockResolvedValue([
      { day: "2026-07-05", login_count: 2 },
      { day: "2026-07-12", login_count: 3 },
    ]);
    const { rerender } = render(intl(<LoginsPage />));
    const totalCard = (await screen.findByText("Total logins")).parentElement as HTMLElement;
    expect(within(totalCard).getByText("2")).toBeInTheDocument();

    nav.search = "from=2026-07-01&to=2026-07-15";
    rerender(intl(<LoginsPage />));
    expect(await within(totalCard).findByText("5")).toBeInTheDocument();
    expect(fetchLoginActivity).toHaveBeenCalledTimes(1);
  });

  it("labels a month bucket by month", async () => {
    nav.search = "range=30d&bucket=month";
    vi.mocked(fetchLoginActivity).mockResolvedValue([{ day: "2026-07-21", login_count: 3 }]);
    renderWithIntl(<LoginsPage />);
    const busiestCard = (await screen.findByText("Busiest month")).parentElement as HTMLElement;
    expect(within(busiestCard).getByText("Jul 2026")).toBeInTheDocument();
  });

  it("labels a week bucket by its Monday", async () => {
    nav.search = "range=30d&bucket=week";
    vi.mocked(fetchLoginActivity).mockResolvedValue([{ day: "2026-07-21", login_count: 3 }]);
    renderWithIntl(<LoginsPage />);
    const busiestCard = (await screen.findByText("Busiest week")).parentElement as HTMLElement;
    expect(within(busiestCard).getByText("Week of Jul 20, 2026")).toBeInTheDocument();
  });
});
