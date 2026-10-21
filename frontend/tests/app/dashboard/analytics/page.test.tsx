import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl-test-utils";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

const nav = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/analytics",
}));

// The plugins installed in the backend build. No PluginProvider is mounted: analytics must not
// depend on the viewer's own plugin switches.
const plugins = vi.hoisted(() => ({ installed: ["chat"] }));
vi.mock("@/lib/plugins/generated", () => ({
  get FRONTEND_PLUGIN_NAMES() {
    return plugins.installed;
  },
}));

vi.mock("@/lib/analytics", async (orig) => ({
  ...(await orig<typeof import("@/lib/analytics")>()),
  fetchSummary: vi.fn(),
  fetchLogins: vi.fn(),
  fetchChatActivity: vi.fn(),
}));

import { fetchChatActivity, fetchLogins, fetchSummary, type SummaryCount } from "@/lib/analytics";
import OverviewPage from "@/app/dashboard/analytics/page";

const summary = vi.mocked(fetchSummary);
const logins = vi.mocked(fetchLogins);
const activity = vi.mocked(fetchChatActivity);
const today = new Date().toISOString().slice(0, 10);

const fig = (over: Partial<SummaryCount>): SummaryCount => ({
  key: "logins",
  label: "Logins",
  view: "logins",
  plugin: null,
  current: 0,
  previous: 0,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  nav.search = "";
  plugins.installed = ["chat"];
  logins.mockResolvedValue([]);
  activity.mockResolvedValue([]);
});

describe("OverviewPage", () => {
  it("renders one card per figure, in the order the server sent", async () => {
    summary.mockResolvedValue([
      fig({ current: 12, previous: 10 }),
      fig({
        key: "active_users",
        label: "Active users",
        view: null,
        current: 3,
        previous: 3,
      }),
    ]);
    renderWithIntl(<OverviewPage />);
    const titles = await screen.findAllByText(/^(Logins|Active users)$/);
    expect(titles.map((t) => t.textContent)).toEqual(["Logins", "Active users"]);
    expect(screen.getByText("+20% vs previous period")).toBeInTheDocument();
  });

  it("links a card to its view, keeping the period, and leaves an unknown view unlinked", async () => {
    nav.search = "range=7d";
    summary.mockResolvedValue([
      fig({ current: 1 }),
      fig({ key: "x", label: "Mystery", view: "nowhere", current: 1 }),
    ]);
    renderWithIntl(<OverviewPage />);
    expect(await screen.findByRole("link", { name: /Logins/ })).toHaveAttribute(
      "href",
      "/dashboard/analytics/logins?range=7d",
    );
    expect(screen.queryByRole("link", { name: /Mystery/ })).toBeNull();
  });

  it("shows every figure the server returns, even from a plugin with no frontend page", async () => {
    plugins.installed = [];
    summary.mockResolvedValue([
      fig({ current: 1 }),
      fig({
        key: "chat.messages",
        label: "Messages sent",
        view: "authoring",
        plugin: "chat",
        current: 5,
      }),
    ]);
    renderWithIntl(<OverviewPage />);
    await screen.findByText("Logins");
    expect(screen.getByText("Messages sent")).toBeInTheDocument();
  });

  it("says new when the previous period was zero, and nothing when both were", async () => {
    summary.mockResolvedValue([
      fig({ current: 4, previous: 0 }),
      fig({
        key: "signups",
        label: "Signups",
        view: null,
        current: 0,
        previous: 0,
      }),
    ]);
    renderWithIntl(<OverviewPage />);
    expect(await screen.findByText("New this period")).toBeInTheDocument();
    expect(screen.getAllByText(/vs previous period|New this period/)).toHaveLength(1);
  });

  it("shows the drop when only the previous period had activity", async () => {
    summary.mockResolvedValue([fig({ current: 0, previous: 5 })]);
    renderWithIntl(<OverviewPage />);
    expect(await screen.findByText("-100% vs previous period")).toBeInTheDocument();
  });

  it("shows the empty state when neither period has any activity", async () => {
    summary.mockResolvedValue([fig({})]);
    renderWithIntl(<OverviewPage />);
    expect(await screen.findByText("No activity in this period.")).toBeInTheDocument();
  });

  it("offers a retry when the summary fails to load", async () => {
    summary.mockRejectedValue(new Error());
    renderWithIntl(<OverviewPage />);
    expect(await screen.findByText("Try again")).toBeInTheDocument();
  });

  describe("activity trend", () => {
    const busyFigures = () => summary.mockResolvedValue([fig({ current: 1 })]);
    const loginRow = { bucket: today, method: "password", login_count: 2 };
    const msgRow = {
      bucket: today,
      event_type: "chat.message_sent",
      event_count: 3,
    } as never;

    it("adds messages sent to logins when chat is enabled", async () => {
      busyFigures();
      logins.mockResolvedValue([loginRow]);
      activity.mockResolvedValue([msgRow]);
      renderWithIntl(<OverviewPage />);
      expect(await screen.findByRole("heading", { name: "Activity" })).toBeInTheDocument();
      expect(screen.getByRole("cell", { name: "5" })).toBeInTheDocument();
    });

    it("counts logins only, and never reads chat, when chat is not installed", async () => {
      plugins.installed = [];
      busyFigures();
      logins.mockResolvedValue([loginRow]);
      renderWithIntl(<OverviewPage />);
      await screen.findByRole("heading", { name: "Activity" });
      expect(screen.getByRole("cell", { name: "2" })).toBeInTheDocument();
      expect(activity).not.toHaveBeenCalled();
    });

    it("shows the error state when the logins read fails", async () => {
      busyFigures();
      logins.mockRejectedValue(new Error());
      renderWithIntl(<OverviewPage />);
      expect(await screen.findByText("Try again")).toBeInTheDocument();
    });
  });
});
