import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  createView,
  deleteView,
  fetchView,
  listViews,
  updateView,
  fetchComposeActivity,
  fetchEventCatalog,
  fetchExplore,
  fetchLogins,
  fetchSummary,
  type ExploreConfig,
} from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";

import { mockFetch, sentRequest } from "@/tests/lib/test-utils";

// authMiddleware reads the stored token; stub it to null so the explicit bearer
// header from the client is what we assert on (mirrors lib/tests/llm.test.ts).
vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("fetchLogins", () => {
  it("GETs /api/v1/analytics/logins for a day range with the bearer token", async () => {
    const points = [{ bucket: "2026-07-20", method: "google", login_count: 3 }];
    const spy = mockFetch(points);

    const result = await fetchLogins("test-token", { from: "2026-07-01", to: "2026-07-20" });

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/analytics/logins");
    expect(url.searchParams.get("from")).toBe("2026-07-01");
    expect(url.searchParams.get("to")).toBe("2026-07-20");
    expect(url.searchParams.get("bucket")).toBe("day");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(points);
  });

  it("wraps a transport failure as an ApiRequestError", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    const error = await fetchLogins("test-token", { from: "2026-07-01", to: "2026-07-20" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toMatch(/unable to connect/i);
  });

  it("propagates an ApiRequestError with its status intact", async () => {
    mockFetch({ detail: "Permission denied" }, 403);

    const error = await fetchLogins("test-token", { from: "2026-07-01", to: "2026-07-20" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(403);
  });
});

describe("fetchComposeActivity", () => {
  it("GETs /api/v1/compose/analytics/activity for a day range with the bearer token", async () => {
    const points = [
      {
        bucket: "2026-07-20",
        event_type: "compose.tool_invoked",
        dimension: "search",
        outcome: null,
        event_count: 2,
      },
    ];
    const spy = mockFetch(points);

    const result = await fetchComposeActivity("test-token", {
      from: "2026-07-01",
      to: "2026-07-20",
    });

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/compose/analytics/activity");
    expect(url.searchParams.get("from")).toBe("2026-07-01");
    expect(url.searchParams.get("to")).toBe("2026-07-20");
    expect(url.searchParams.get("bucket")).toBe("day");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(points);
  });

  it("propagates an ApiRequestError with its status intact", async () => {
    mockFetch({ detail: "Permission denied" }, 403);

    const error = await fetchComposeActivity("test-token", {
      from: "2026-07-01",
      to: "2026-07-20",
    }).catch((e: unknown) => e);

    expect((error as ApiRequestError).status).toBe(403);
  });
});

describe("fetchSummary", () => {
  it("GETs /api/v1/analytics/summary for a range, with no bucket, and the bearer token", async () => {
    const counts = [
      {
        key: "logins",
        label: "Logins",
        view: "logins",
        plugin: null,
        current: 3,
        previous: 1,
      },
    ];
    const spy = mockFetch(counts);

    const result = await fetchSummary("test-token", {
      from: "2026-07-01",
      to: "2026-07-20",
    });

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/analytics/summary");
    expect(url.searchParams.get("from")).toBe("2026-07-01");
    expect(url.searchParams.get("to")).toBe("2026-07-20");
    expect(url.searchParams.has("bucket")).toBe(false);
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(counts);
  });
});

describe("fetchEventCatalog", () => {
  it("GETs /api/v1/analytics/events with the bearer token", async () => {
    const catalog = [{ event_type: "x", fields: [] }];
    const spy = mockFetch(catalog);

    const result = await fetchEventCatalog("test-token");

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/analytics/events");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(catalog);
  });
});

describe("fetchExplore", () => {
  const period = { from: "2026-07-01", to: "2026-07-20", bucket: "week" } as const;
  const bare: ExploreConfig = {
    event: "compose.tool_invoked",
    actor: null,
    filters: [],
    measure: "count",
    groupBy: null,
    chart: "line",
  };
  const empty = { points: [], totals: [], truncated: false, actor_names: {} };

  it("sends the period, event and measure, and nothing unset", async () => {
    const spy = mockFetch(empty);

    await fetchExplore("test-token", period, bare);

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/analytics/query");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      from: "2026-07-01",
      to: "2026-07-20",
      bucket: "week",
      event_type: "compose.tool_invoked",
      measure: "count",
    });
  });

  it("sends the actor, each filter and the grouping when set", async () => {
    const spy = mockFetch(empty);

    await fetchExplore("test-token", period, {
      ...bare,
      actor: "42",
      filters: [
        { field: "outcome", value: "failed" },
        { field: "outcome", value: "null" },
      ],
      measure: "distinct_actors",
      groupBy: "actor",
    });

    const params = new URL(sentRequest(spy).url).searchParams;
    expect(params.get("actor_id")).toBe("42");
    expect(params.getAll("filter")).toEqual(["outcome:failed", "outcome:null"]);
    expect(params.get("measure")).toBe("distinct_actors");
    expect(params.get("group_by")).toBe("actor");
  });
});

describe("saved views", () => {
  const config: ExploreConfig = {
    event: "auth.login",
    actor: null,
    filters: [],
    measure: "count",
    groupBy: null,
    chart: "line",
  };
  const view = { id: "v1", name: "Logins", config, created_at: "", updated_at: "" };

  it("lists the caller's views", async () => {
    const spy = mockFetch([view]);
    expect(await listViews("test-token")).toEqual([view]);
    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/analytics/views");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
  });

  it("fetches one view by id", async () => {
    const spy = mockFetch(view);
    expect(await fetchView("test-token", "v1")).toEqual(view);
    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/analytics/views/v1");
  });

  it("POSTs a new view with its name and config", async () => {
    const spy = mockFetch(view, 201);
    expect(await createView("test-token", "Logins", config)).toEqual(view);
    const request = sentRequest(spy);
    expect(request.method).toBe("POST");
    expect(await request.json()).toEqual({ name: "Logins", config });
  });

  it("PATCHes only the parts given", async () => {
    const spy = mockFetch(view);
    await updateView("test-token", "v1", { name: "Renamed" });
    const request = sentRequest(spy);
    expect(request.method).toBe("PATCH");
    expect(new URL(request.url).pathname).toBe("/api/v1/analytics/views/v1");
    expect(await request.json()).toEqual({ name: "Renamed" });
  });

  it("DELETEs a view", async () => {
    const spy = mockFetch(null, 204);
    await deleteView("test-token", "v1");
    expect(sentRequest(spy).method).toBe("DELETE");
    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/analytics/views/v1");
  });

  it("rejects with the status when the view is missing", async () => {
    mockFetch({ detail: "not found" }, 404);
    const error = await fetchView("test-token", "v1").catch((e: unknown) => e);
    expect((error as ApiRequestError).status).toBe(404);
  });
});
