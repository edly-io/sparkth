import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl-test-utils";
import { ApiRequestError } from "@/lib/api";

vi.mock("@/core/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));
const checkPermission = vi.hoisted(() => vi.fn());
vi.mock("@/lib/permissions/client", () => ({ checkPermission }));
const audit = vi.hoisted(() => ({
  fetchAuditEvents: vi.fn(),
  fetchAuditEvent: vi.fn(),
  fetchAuditCategories: vi.fn(),
  exportAuditEvents: vi.fn(),
}));
vi.mock("@/lib/audit", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/audit")>()),
  ...audit,
}));
const downloadBlob = vi.hoisted(() => vi.fn());
vi.mock("@/lib/download", () => ({ downloadBlob }));

import AuditLogPage from "@/app/dashboard/audit/AuditLogPage";

function event(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    occurred_at: "2026-10-18T09:00:00Z",
    category: "auth",
    action: "login",
    source: "rest",
    actor_type: "user",
    actor_id: "7",
    actor_label: "alice",
    outcome: "success",
    target_type: null,
    target_id: null,
    ...overrides,
  };
}

function record(id: number, overrides: Record<string, unknown> = {}) {
  return {
    ...event(id),
    request_ip: "10.0.0.1",
    user_agent: null,
    request_id: null,
    error_detail: null,
    old_values: null,
    new_values: { value: "@example.com" },
    tool_name: null,
    tool_args: null,
    model_provider: null,
    model_name: null,
    model_version: null,
    purpose: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  checkPermission.mockResolvedValue(true);
  audit.fetchAuditCategories.mockResolvedValue(["auth", "tool"]);
});

describe("AuditLogPage", () => {
  it("checks audit.read and lists events", async () => {
    audit.fetchAuditEvents.mockResolvedValue({
      items: [event(2)],
      next_before_id: null,
    });

    renderWithIntl(<AuditLogPage />);

    expect(await screen.findByText("auth.login")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(checkPermission).toHaveBeenCalledWith("test-token", "audit.read", {});
    expect(audit.fetchAuditEvents).toHaveBeenCalledWith("test-token", {}, undefined);
  });

  it("shows the 403 view when denied", async () => {
    checkPermission.mockResolvedValue(false);

    renderWithIntl(<AuditLogPage />);

    expect(
      await screen.findByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
    expect(audit.fetchAuditEvents).not.toHaveBeenCalled();
  });

  it("refetches with the filters on apply and expands a row's details", async () => {
    audit.fetchAuditEvents.mockResolvedValue({
      items: [event(2)],
      next_before_id: null,
    });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("auth.login");

    fireEvent.change(screen.getByLabelText("Category"), {
      target: { value: "auth" },
    });
    fireEvent.change(screen.getByLabelText("Outcome"), {
      target: { value: "failure" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(audit.fetchAuditEvents).toHaveBeenLastCalledWith(
        "test-token",
        expect.objectContaining({ category: "auth", outcome: "failure" }),
        undefined,
      ),
    );
  });

  it("fetches a row's full details when it is expanded", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [event(2)], next_before_id: null });
    audit.fetchAuditEvent.mockResolvedValue(record(2));
    renderWithIntl(<AuditLogPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Show details" }));

    expect(await screen.findByText(/@example\.com/)).toBeInTheDocument();
    expect(audit.fetchAuditEvent).toHaveBeenCalledWith("test-token", 2);

    fireEvent.click(screen.getByRole("button", { name: "Hide details" }));
    fireEvent.click(screen.getByRole("button", { name: "Show details" }));
    expect(await screen.findByText(/@example\.com/)).toBeInTheDocument();
    expect(audit.fetchAuditEvent).toHaveBeenCalledTimes(1);
  });

  it("says so when a row's details fail to load", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [event(2)], next_before_id: null });
    audit.fetchAuditEvent.mockRejectedValue(new Error("boom"));
    renderWithIntl(<AuditLogPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Show details" }));

    expect(await screen.findByText("We couldn't load this event's details.")).toBeInTheDocument();
  });

  it("loads older events with the cursor", async () => {
    audit.fetchAuditEvents
      .mockResolvedValueOnce({ items: [event(2)], next_before_id: 2 })
      .mockResolvedValueOnce({
        items: [event(1, { action: "email_verified" })],
        next_before_id: null,
      });
    renderWithIntl(<AuditLogPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Load more" }));

    expect(await screen.findByText("auth.email_verified")).toBeInTheDocument();
    expect(screen.getByText("auth.login")).toBeInTheDocument();
    expect(audit.fetchAuditEvents).toHaveBeenLastCalledWith("test-token", {}, 2);
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("offers the categories the API lists, and one 'Any' outcome", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [], next_before_id: null });
    renderWithIntl(<AuditLogPage />);

    const category = await screen.findByLabelText("Category");
    await waitFor(() =>
      expect(
        Array.from((category as HTMLSelectElement).options).map((option) => option.value),
      ).toEqual(["", "auth", "tool"]),
    );
    const outcome = screen.getByLabelText("Outcome") as HTMLSelectElement;
    expect(Array.from(outcome.options).filter((option) => option.value === "")).toHaveLength(1);
  });

  it("stretches 'to' to the end of the chosen minute", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [], next_before_id: null });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("No audit events match these filters.");

    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-10-20T10:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    const endOfMinute = new Date(new Date("2026-10-20T10:30").getTime() + 59_999).toISOString();
    await waitFor(() =>
      expect(audit.fetchAuditEvents).toHaveBeenLastCalledWith(
        "test-token",
        { to: endOfMinute },
        undefined,
      ),
    );
  });

  it("drops an older page that lands after the filters changed", async () => {
    let resolveOlder: (page: unknown) => void = () => {};
    audit.fetchAuditEvents
      .mockResolvedValueOnce({ items: [event(2)], next_before_id: 2 })
      .mockReturnValueOnce(new Promise((resolve) => (resolveOlder = resolve)))
      .mockResolvedValueOnce({
        items: [event(5, { category: "tool", action: "invoked" })],
        next_before_id: null,
      });
    renderWithIntl(<AuditLogPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Load more" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("tool.invoked")).toBeInTheDocument();
    resolveOlder({ items: [event(1, { action: "email_verified" })], next_before_id: 1 });

    await waitFor(() => expect(screen.queryByText("auth.login")).not.toBeInTheDocument());
    expect(screen.queryByText("auth.email_verified")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("flags an actor id that isn't a number and won't apply it", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [], next_before_id: null });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("No audit events match these filters.");

    fireEvent.change(screen.getByLabelText("Actor user ID"), { target: { value: "abc" } });

    expect(screen.getByText("Actor user ID must be a number.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
    // Enter in a field submits the form without clicking Apply.
    fireEvent.submit(screen.getByLabelText("Actor user ID"));
    expect(audit.fetchAuditEvents).toHaveBeenCalledTimes(1);
  });

  it("applies a numeric actor id, trimmed", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [], next_before_id: null });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("No audit events match these filters.");

    fireEvent.change(screen.getByLabelText("Actor user ID"), { target: { value: " 42 " } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(audit.fetchAuditEvents).toHaveBeenLastCalledWith(
        "test-token",
        { actor_id: "42" },
        undefined,
      ),
    );
  });

  it("flags a range that ends before it starts and won't apply it", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [], next_before_id: null });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("No audit events match these filters.");

    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-10-20T10:30" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-10-20T10:29" } });

    expect(
      screen.getByText("The start time must be on or before the end time."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
  });

  it("accepts a range that starts and ends in the same minute", async () => {
    audit.fetchAuditEvents.mockResolvedValue({ items: [], next_before_id: null });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("No audit events match these filters.");

    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-10-20T10:30" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-10-20T10:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    const start = new Date("2026-10-20T10:30");
    await waitFor(() =>
      expect(audit.fetchAuditEvents).toHaveBeenLastCalledWith(
        "test-token",
        { from: start.toISOString(), to: new Date(start.getTime() + 59_999).toISOString() },
        undefined,
      ),
    );
  });

  it("shows only the error when a refetch fails", async () => {
    audit.fetchAuditEvents
      .mockResolvedValueOnce({ items: [event(2)], next_before_id: 2 })
      .mockRejectedValueOnce(
        new ApiRequestError({ message: "Server exploded", fieldErrors: {} }, 500),
      );
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("auth.login");

    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(await screen.findByText("Server exploded")).toBeInTheDocument();
    expect(screen.queryByText("auth.login")).not.toBeInTheDocument();
    expect(screen.queryByText("No audit events match these filters.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("keeps the empty state hidden when an export follows a failed load", async () => {
    audit.fetchAuditEvents.mockRejectedValueOnce(
      new ApiRequestError({ message: "Server exploded", fieldErrors: {} }, 500),
    );
    const blob = new Blob(["id\r\n"]);
    audit.exportAuditEvents.mockResolvedValue({ blob, filename: "audit-events.csv" });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("Server exploded");

    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledWith(blob, "audit-events.csv"));
    expect(screen.queryByText("No audit events match these filters.")).not.toBeInTheDocument();
  });

  it("keeps the loaded rows when loading more fails", async () => {
    audit.fetchAuditEvents
      .mockResolvedValueOnce({ items: [event(2)], next_before_id: 2 })
      .mockRejectedValueOnce(
        new ApiRequestError({ message: "Server exploded", fieldErrors: {} }, 500),
      );
    renderWithIntl(<AuditLogPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Load more" }));

    expect(await screen.findByText("Server exploded")).toBeInTheDocument();
    expect(screen.getByText("auth.login")).toBeInTheDocument();
  });

  it("exports with the applied filters under the server's filename", async () => {
    audit.fetchAuditEvents.mockResolvedValue({
      items: [],
      next_before_id: null,
    });
    const blob = new Blob(["id\r\n"]);
    audit.exportAuditEvents.mockResolvedValue({
      blob,
      filename: "audit-events-20261020T101500Z.jsonl",
    });
    renderWithIntl(<AuditLogPage />);
    await screen.findByText("No audit events match these filters.");

    fireEvent.click(screen.getByRole("button", { name: "Export JSON Lines" }));

    await waitFor(() =>
      expect(downloadBlob).toHaveBeenCalledWith(blob, "audit-events-20261020T101500Z.jsonl"),
    );
    expect(audit.exportAuditEvents).toHaveBeenCalledWith("test-token", {}, "jsonl");
  });
});
