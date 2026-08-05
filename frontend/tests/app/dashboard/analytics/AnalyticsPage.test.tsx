import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { redirect } from "next/navigation";

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

// Denied access redirects; stub redirect so we can assert it (and keep render from navigating).
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));

import { fetchLoginActivity, type LoginActivityPoint } from "@/lib/analytics";
import AnalyticsPage from "@/app/dashboard/analytics/AnalyticsPage";

beforeEach(() => {
  vi.clearAllMocks();
  auth.token = "test-token";
});

describe("AnalyticsPage states", () => {
  it("shows a loading indicator, then the chart and stats", async () => {
    // Two points with distinct counts so the "Total logins" (5) and "Busiest
    // day" (3) stat tiles render different text — a single point would make
    // both tiles show the same value and collide on the `findByText("5")` query.
    vi.mocked(fetchLoginActivity).mockResolvedValue([
      { day: "2026-07-23", login_count: 3 },
      { day: "2026-07-22", login_count: 2 },
    ]);

    const { container } = render(<AnalyticsPage />);

    // loading first
    expect(screen.getByText(/loading/i)).toBeInTheDocument();

    // then content: total logins stat + a chart
    expect(await screen.findByText("5")).toBeInTheDocument();
    await waitFor(() => expect(container.querySelector("svg[role='img']")).toBeInTheDocument());
  });

  it("shows an empty state when there are no logins", async () => {
    vi.mocked(fetchLoginActivity).mockResolvedValue([]);

    render(<AnalyticsPage />);

    expect(await screen.findByText(/no logins in the last 30 days/i)).toBeInTheDocument();
  });

  it("labels the window as UTC in the subheading so dates are not misread across timezones", () => {
    vi.mocked(fetchLoginActivity).mockResolvedValue([]);

    render(<AnalyticsPage />);

    // Dates are UTC-bucketed server-side (see lib/analytics reads); the subheading must say
    // so, or a user in another timezone reads the last bar as "today" and it disagrees.
    expect(screen.getByText(/over the last 30 days \(UTC\)/i)).toBeInTheDocument();
  });

  it("redirects to the dashboard on 403 without disclosing permission details", async () => {
    vi.mocked(fetchLoginActivity).mockRejectedValue(
      new ApiRequestError({ message: "Permission denied", fieldErrors: {} }, 403),
    );

    render(<AnalyticsPage />);

    await waitFor(() => expect(redirect).toHaveBeenCalledWith("/dashboard"));
    // No permission name is disclosed anywhere.
    expect(screen.queryByText(/analytics\.read/i)).not.toBeInTheDocument();
  });

  it("shows a generic error on other failures", async () => {
    vi.mocked(fetchLoginActivity).mockRejectedValue(
      new ApiRequestError({ message: "boom", fieldErrors: {} }, 500),
    );

    render(<AnalyticsPage />);

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

    render(<AnalyticsPage />);

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));

    expect(await screen.findByText("Total logins")).toBeInTheDocument();
    expect(fetchLoginActivity).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });
});

describe("AnalyticsPage stat/chart window consistency", () => {
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
    // chart built by buildDailySeries only spans [today-29 .. today] (oldest slot 2026-06-25),
    // so that boundary day has no bar. Only 2026-07-23 is inside the chart's window.
    vi.mocked(fetchLoginActivity).mockResolvedValue([
      { day: "2026-06-24", login_count: 5 },
      { day: "2026-07-23", login_count: 2 },
    ]);

    render(<AnalyticsPage />);

    const totalCard = (await screen.findByText("Total logins")).parentElement as HTMLElement;
    // Windowed total is 2 (only 2026-07-23), not 7 (5 + 2 from the raw response).
    expect(within(totalCard).getByText("2")).toBeInTheDocument();

    const busiestCard = screen.getByText("Busiest day").parentElement as HTMLElement;
    // Busiest in-window day is 2026-07-23 (count 2), not the out-of-window 2026-06-24 (count 5).
    expect(within(busiestCard).getByText("2")).toBeInTheDocument();
    expect(within(busiestCard).getByText("2026-07-23")).toBeInTheDocument();

    expect(screen.queryByText("2026-06-24")).not.toBeInTheDocument();
    expect(screen.queryByText("7")).not.toBeInTheDocument();
  });
});

describe("AnalyticsPage empty-window composition", () => {
  it("shows the empty state when the API returns rows but all fall outside the chart window", async () => {
    vi.mocked(fetchLoginActivity).mockResolvedValue([{ day: "2000-01-01", login_count: 5 }]);

    render(<AnalyticsPage />);

    expect(await screen.findByText(/no logins in the last 30 days/i)).toBeInTheDocument();
    expect(screen.queryByText("Total logins")).not.toBeInTheDocument();
    expect(screen.queryByText("Busiest day")).not.toBeInTheDocument();
  });
});

describe("AnalyticsPage stale-response guard", () => {
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
    const { rerender } = render(<AnalyticsPage />); // fetches with token-A (first, pending)

    auth.token = "token-B";
    rerender(<AnalyticsPage />); // token changed → refetch with token-B (second, pending)

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

describe("AnalyticsPage window stability", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps the window pinned to the fetched data across an unrelated re-render", async () => {
    vi.mocked(fetchLoginActivity).mockResolvedValue([{ day: "2026-06-25", login_count: 5 }]);

    const { rerender } = render(<AnalyticsPage />);

    const totalCard = (await screen.findByText("Total logins")).parentElement as HTMLElement;
    expect(within(totalCard).getByText("5")).toBeInTheDocument();

    // A day passes, then something unrelated re-renders the page (same `points`).
    vi.setSystemTime(new Date("2026-07-25T12:00:00Z"));
    rerender(<AnalyticsPage />);

    expect(within(totalCard).getByText("5")).toBeInTheDocument();
    const busiestCard = screen.getByText("Busiest day").parentElement as HTMLElement;
    expect(within(busiestCard).getByText("2026-06-25")).toBeInTheDocument();
  });
});
