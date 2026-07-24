import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";

import { ApiRequestError } from "@/lib/api";

// Auth: a fixed token so the page's fetch effect runs.
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

// Analytics data access: keep the real types, stub the fetch.
vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return { ...actual, fetchLoginActivity: vi.fn() };
});

import { fetchLoginActivity } from "@/lib/analytics";
import AnalyticsPage, { buildDailySeries, summarize } from "./AnalyticsPage";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("buildDailySeries", () => {
  it("zero-fills a continuous oldest→newest series over the window", () => {
    const now = new Date("2026-07-23T12:00:00Z");
    const points = [
      { day: "2026-07-23", login_count: 5 },
      { day: "2026-07-21", login_count: 2 },
    ];

    const series = buildDailySeries(points, 3, now);

    expect(series).toEqual([
      { label: "2026-07-21", value: 2 },
      { label: "2026-07-22", value: 0 },
      { label: "2026-07-23", value: 5 },
    ]);
  });
});

describe("summarize", () => {
  it("derives total logins and the busiest day from a windowed series", () => {
    // Takes the already-windowed BarChartDatum[] (as produced by buildDailySeries), not raw
    // API points, so it can never see a day outside the chart's window.
    const series = [
      { label: "2026-07-21", value: 2 },
      { label: "2026-07-22", value: 0 },
      { label: "2026-07-23", value: 5 },
    ];

    const { total, busiest } = summarize(series);

    expect(total).toBe(7);
    expect(busiest).toEqual({ label: "2026-07-23", value: 5 });
  });

  it("returns zero total and null busiest for an empty series", () => {
    expect(summarize([])).toEqual({ total: 0, busiest: null });
  });
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

  it("shows a permission message on 403", async () => {
    vi.mocked(fetchLoginActivity).mockRejectedValue(
      new ApiRequestError({ message: "Permission denied", fieldErrors: {} }, 403),
    );

    render(<AnalyticsPage />);

    expect(await screen.findByText(/analytics\.read/i)).toBeInTheDocument();
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
