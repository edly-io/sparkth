import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const nav = vi.hoisted(() => ({ search: "", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: nav.replace }),
}));

import AnalyticsIndex from "@/app/dashboard/analytics/page";

beforeEach(() => {
  nav.search = "";
  nav.replace.mockReset();
});

describe("AnalyticsIndex", () => {
  it("forwards to the Logins view", () => {
    render(<AnalyticsIndex />);
    expect(nav.replace).toHaveBeenCalledWith("/dashboard/analytics/logins");
  });

  it("keeps the period query when forwarding", () => {
    nav.search = "range=7d&bucket=week";
    render(<AnalyticsIndex />);
    expect(nav.replace).toHaveBeenCalledWith("/dashboard/analytics/logins?range=7d&bucket=week");
  });
});
