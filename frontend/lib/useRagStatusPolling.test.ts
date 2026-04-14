import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useRagStatusPolling } from "./useRagStatusPolling";

vi.mock("./drive", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./drive")>();
  return {
    ...actual,
    getFolderRagStatus: vi.fn(),
  };
});

import { getFolderRagStatus } from "./drive";

beforeEach(() => {
  vi.mocked(getFolderRagStatus).mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useRagStatusPolling", () => {
  it("fetches rag statuses on mount", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "ready", rag_error: null }],
    });

    const { result } = renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toEqual({ status: "ready", error: null });
    });
  });

  it("maps multiple files correctly", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [
        { file_id: 10, name: "a.pdf", rag_status: "ready", rag_error: null },
        { file_id: 20, name: "b.txt", rag_status: "processing", rag_error: null },
        { file_id: 30, name: "c.pdf", rag_status: "failed", rag_error: "Download failed" },
      ],
    });

    const { result } = renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toEqual({ status: "ready", error: null });
      expect(result.current.ragStatuses[20]).toEqual({ status: "processing", error: null });
      expect(result.current.ragStatuses[30]).toEqual({
        status: "failed",
        error: "Download failed",
      });
    });
  });

  it("returns empty ragStatuses initially", () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({ folder_id: 1, files: [] });

    const { result } = renderHook(() => useRagStatusPolling(1, "token"));

    expect(result.current.ragStatuses).toEqual({});
  });

  it("does not fetch when folderId is null", () => {
    renderHook(() => useRagStatusPolling(null, "token"));

    expect(getFolderRagStatus).not.toHaveBeenCalled();
  });

  it("does not fetch when token is null", () => {
    renderHook(() => useRagStatusPolling(1, null));

    expect(getFolderRagStatus).not.toHaveBeenCalled();
  });

  it("stops polling when folder is empty", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({ folder_id: 1, files: [] });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      expect(getFolderRagStatus).toHaveBeenCalled();
    });

    const pollTimeout = setTimeoutSpy.mock.calls.find((call) => call[1] === 5000);
    expect(pollTimeout).toBeUndefined();
  });

  it("stops polling when all files are terminal (ready/failed)", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [
        { file_id: 10, name: "a.pdf", rag_status: "ready", rag_error: null },
        { file_id: 20, name: "b.pdf", rag_status: "failed", rag_error: null },
      ],
    });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      expect(getFolderRagStatus).toHaveBeenCalled();
    });

    const pollTimeout = setTimeoutSpy.mock.calls.find((call) => call[1] === 5000);
    expect(pollTimeout).toBeUndefined();
  });

  it("stops polling when all files have null status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "a.pdf", rag_status: null, rag_error: null }],
    });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      expect(getFolderRagStatus).toHaveBeenCalled();
    });

    const pollTimeout = setTimeoutSpy.mock.calls.find((call) => call[1] === 5000);
    expect(pollTimeout).toBeUndefined();
  });

  it("schedules next poll when files are non-terminal", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "a.pdf", rag_status: "processing", rag_error: null }],
    });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      const pollTimeout = setTimeoutSpy.mock.calls.find((call) => call[1] === 5000);
      expect(pollTimeout).toBeDefined();
    });
  });

  it("clears timeout on unmount", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "a.pdf", rag_status: "processing", rag_error: null }],
    });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");

    const { unmount } = renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      expect(setTimeoutSpy.mock.calls.find((c) => c[1] === 5000)).toBeDefined();
    });

    unmount();
    expect(clearTimeoutSpy).toHaveBeenCalled();
  });

  it("restarts polling when restart() is called", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "a.pdf", rag_status: "ready", rag_error: null }],
    });

    const { result } = renderHook(() => useRagStatusPolling(1, "token"));

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toEqual({ status: "ready", error: null });
    });

    const callsBefore = vi.mocked(getFolderRagStatus).mock.calls.length;

    act(() => result.current.restart());

    await waitFor(() => {
      expect(vi.mocked(getFolderRagStatus).mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it("resets statuses on new folderId", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "a.pdf", rag_status: "ready", rag_error: null }],
    });

    const { result, rerender } = renderHook(
      ({ folderId }: { folderId: number | null }) => useRagStatusPolling(folderId, "token"),
      { initialProps: { folderId: 1 } },
    );

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toBeDefined();
    });

    vi.mocked(getFolderRagStatus).mockResolvedValue({ folder_id: 2, files: [] });

    rerender({ folderId: 2 });

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toBeUndefined();
    });
  });
});
