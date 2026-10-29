import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  AUDIT_OUTCOMES,
  AUDIT_SOURCES,
  exportAuditEvents,
  fetchAuditCategories,
  fetchAuditEvent,
  fetchAuditEvents,
} from "@/lib/audit";
import { ApiRequestError } from "@/lib/api";

import { mockFetch, sentRequest } from "@/tests/lib/test-utils";

vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("fetchAuditEvents", () => {
  it("GETs /api/v1/audit/events with only the filters that are set", async () => {
    const page = { items: [], next_before_id: null };
    const spy = mockFetch(page);

    const result = await fetchAuditEvents(
      "test-token",
      { category: "auth", outcome: "failure", actor_id: "" },
      42,
    );

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/audit/events");
    expect(url.searchParams.get("category")).toBe("auth");
    expect(url.searchParams.get("outcome")).toBe("failure");
    expect(url.searchParams.get("before_id")).toBe("42");
    expect(url.searchParams.has("actor_id")).toBe(false);
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(page);
  });

  it("propagates an ApiRequestError with its status intact", async () => {
    mockFetch({ detail: "Permission denied" }, 403);

    const error = await fetchAuditEvents("test-token", {}).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(403);
  });
});

describe("fetchAuditEvent", () => {
  it("GETs /api/v1/audit/events/{id}", async () => {
    const record = { id: 42, category: "auth", action: "login" };
    const spy = mockFetch(record);

    const result = await fetchAuditEvent("test-token", 42);

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/audit/events/42");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(record);
  });
});

describe("fetchAuditCategories", () => {
  it("GETs /api/v1/audit/categories", async () => {
    const spy = mockFetch(["auth", "tool"]);

    const categories = await fetchAuditCategories("test-token");

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/audit/categories");
    expect(categories).toEqual(["auth", "tool"]);
  });
});

describe("filter choices", () => {
  it("offers every outcome and source the backend accepts", () => {
    expect(AUDIT_OUTCOMES).toEqual(["success", "failure", "denied"]);
    expect(AUDIT_SOURCES).toEqual(["rest", "mcp", "compose", "rag", "cli", "system"]);
  });
});

describe("exportAuditEvents", () => {
  it("GETs the export in the requested format and keeps the server's filename", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response('{"id":1}\n', {
        status: 200,
        headers: {
          "Content-Disposition": 'attachment; filename="audit-events-20261020T101500Z.jsonl"',
        },
      }),
    );

    const { blob, filename } = await exportAuditEvents("test-token", { source: "rest" }, "jsonl");

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/audit/events/export");
    expect(url.searchParams.get("format")).toBe("jsonl");
    expect(url.searchParams.get("source")).toBe("rest");
    expect(await blob.text()).toBe('{"id":1}\n');
    expect(filename).toBe("audit-events-20261020T101500Z.jsonl");
  });

  it("falls back to a generic filename when the server names none", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("id\r\n", { status: 200 }));

    const { filename } = await exportAuditEvents("test-token", {}, "csv");

    expect(filename).toBe("audit-events.csv");
  });
});
