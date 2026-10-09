import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { getActivityEmbedUrl, listActivities } from "@/plugins/pxc/client";
import { mockFetch, sentRequest } from "@/tests/lib/test-utils";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

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

describe("getActivityEmbedUrl", () => {
  it("GETs the launch for the given permission and returns its embed URL", async () => {
    const spy = mockFetch({ embed_url: "/api/v1/pxc/embed?token=abc" });

    const url = await getActivityEmbedUrl("test-token", "act-1", "edit");

    const request = new URL(sentRequest(spy).url);
    expect(request.pathname).toBe("/api/v1/pxc/activities/act-1/launch");
    expect(request.searchParams.get("permission")).toBe("edit");
    expect(url).toBe("/api/v1/pxc/embed?token=abc");
  });

  it("surfaces a 404 as an ApiRequestError carrying the status", async () => {
    mockFetch({ detail: "Activity not found" }, 404);

    const error = await getActivityEmbedUrl("test-token", "missing", "play").catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(404);
  });
});
