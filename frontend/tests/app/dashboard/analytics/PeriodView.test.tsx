import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";

import en from "@/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

import { ApiRequestError } from "@/lib/api";

const auth = vi.hoisted(() => ({ token: "test-token" }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: auth.token }),
}));

const nav = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/analytics/x",
}));

import { PeriodView, type PeriodData } from "@/app/dashboard/analytics/PeriodView";

type Row = { n: number };
const fetcher = vi.fn<(token: string, range: { from: string; to: string }) => Promise<Row[]>>();
const children = vi.fn((d: PeriodData<Row>) => (
  <p>
    ready {d.current.map((r) => r.n).join(",")} / {d.previous.map((r) => r.n).join(",")}
  </p>
));

function view() {
  return (
    <PeriodView title="Things" subtitle={(range) => `During ${range}`} fetcher={fetcher}>
      {children}
    </PeriodView>
  );
}

const CURRENT_TO = "2026-07-10";
const forbidden = new ApiRequestError({ message: "Permission denied", fieldErrors: {} }, 403);

beforeEach(() => {
  vi.clearAllMocks();
  auth.token = "test-token";
  nav.search = "from=2026-07-01&to=2026-07-10&bucket=week";
  fetcher.mockImplementation(async (_t, { to }) => (to === CURRENT_TO ? [{ n: 1 }] : [{ n: 2 }]));
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("PeriodView", () => {
  it("shows the header and a spinner, then passes both periods to children", async () => {
    renderWithIntl(view());

    expect(screen.getByRole("heading", { name: "Things" })).toBeInTheDocument();
    expect(screen.getByText(/^During Jul 1/)).toBeInTheDocument();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(await screen.findByText("ready 1 / 2")).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith("test-token", {
      from: "2026-07-01",
      to: "2026-07-10",
    });
    expect(fetcher).toHaveBeenCalledWith("test-token", {
      from: "2026-06-21",
      to: "2026-06-30",
    });
    expect(children).toHaveBeenLastCalledWith({
      current: [{ n: 1 }],
      previous: [{ n: 2 }],
      from: "2026-07-01",
      to: "2026-07-10",
      bucket: "week",
    });
  });

  it.each([
    ["the current", CURRENT_TO],
    ["the previous", "2026-06-30"],
  ])("shows the access view when %s period is forbidden", async (_name, deniedTo) => {
    fetcher.mockImplementation(async (_t, { to }) => {
      if (to === deniedTo) throw forbidden;
      return [];
    });
    renderWithIntl(view());
    expect(
      await screen.findByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
    expect(children).not.toHaveBeenCalled();
  });

  it("refetches both periods when retry is pressed after an error", async () => {
    fetcher.mockRejectedValueOnce(new ApiRequestError({ message: "boom", fieldErrors: {} }, 500));
    renderWithIntl(view());

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));

    expect(await screen.findByText("ready 1 / 2")).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(4);
  });

  it("ignores a stale response that resolves after a token change", async () => {
    let resolveFirst!: (rows: Row[]) => void;
    fetcher.mockImplementation((token, { to }) => {
      if (to !== CURRENT_TO) return Promise.resolve([]);
      if (token === "token-A") return new Promise((r) => (resolveFirst = r));
      return Promise.resolve([{ n: 5 }]);
    });

    auth.token = "token-A";
    const { rerender } = renderWithIntl(view());
    auth.token = "token-B";
    rerender(
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
        {view()}
      </NextIntlClientProvider>,
    );
    expect(await screen.findByText("ready 5 /")).toBeInTheDocument();

    await act(async () => resolveFirst([{ n: 9 }]));
    expect(screen.getByText("ready 5 /")).toBeInTheDocument();
    expect(screen.queryByText(/ready 9/)).not.toBeInTheDocument();
  });
});
