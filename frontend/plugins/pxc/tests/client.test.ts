import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { deleteActivity, getActivityLaunch, listActivities } from "@/plugins/pxc/src/client";
import { mockFetch, sentRequest } from "@/lib/testing/fetch";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("listActivities", () => {
  it("GETs the user's activities with the bearer token", async () => {
    const activities = [
      {
        id: "0192f0c4-0000-7000-8000-000000000001",
        title: "Photosynthesis quiz",
        description: "Five questions",
        created_at: "2026-09-30T12:00:00Z",
        preview_url: "/dashboard/pxc?activity=0192f0c4-0000-7000-8000-000000000001",
      },
    ];
    const spy = mockFetch(activities);

    const result = await listActivities("test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/pxc/activities");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(activities);
  });
});

describe("getActivityLaunch", () => {
  it("GETs the launch for the given permission and returns it, owner included", async () => {
    const launch = { embed_url: "/api/v1/pxc/embed?token=abc", owner_user_id: 7 };
    const spy = mockFetch(launch);

    const result = await getActivityLaunch("test-token", "act-1", "edit");

    const request = new URL(sentRequest(spy).url);
    expect(request.pathname).toBe("/api/v1/pxc/activities/act-1/launch");
    expect(request.searchParams.get("permission")).toBe("edit");
    expect(result).toEqual(launch);
  });

  it("surfaces a 404 as an ApiRequestError carrying the status", async () => {
    mockFetch({ detail: "Activity not found" }, 404);

    const error = await getActivityLaunch("test-token", "missing", "play").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(404);
  });
});

describe("deleteActivity", () => {
  it("DELETEs the activity with the bearer token", async () => {
    const spy = mockFetch(null, 204);

    await deleteActivity("test-token", "act-1");

    const request = sentRequest(spy);
    expect(request.method).toBe("DELETE");
    expect(new URL(request.url).pathname).toBe("/api/v1/pxc/activities/act-1");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
  });

  it("surfaces a 404 as an ApiRequestError carrying the status", async () => {
    mockFetch({ detail: "Activity not found" }, 404);

    const error = await deleteActivity("test-token", "missing").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(404);
  });
});
