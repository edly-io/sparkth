import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useRagStatusPolling } from "@/lib/useRagStatusPolling";

vi.mock("@/lib/drive", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/drive")>();
  return {
    ...actual,
    getFolderRagStatus: vi.fn(),
  };
});

import { getFolderRagStatus } from "@/lib/drive";

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

    const { result } = renderHook(() => useRagStatusPolling([1], "token"));

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

    const { result } = renderHook(() => useRagStatusPolling([1], "token"));

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toEqual({ status: "ready", error: null });
      expect(result.current.ragStatuses[20]).toEqual({ status: "processing", error: null });
      expect(result.current.ragStatuses[30]).toEqual({
        status: "failed",
        error: "Download failed",
      });
    });
  });

  it("returns empty ragStatuses initially", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({ folder_id: 1, files: [] });

    const { result } = renderHook(() => useRagStatusPolling([1], "token"));

    expect(result.current.ragStatuses).toEqual({});

    // Flush the mount-triggered poll so its state update settles inside act().
    await act(async () => {});
  });

  it("does not fetch when folderIds is empty", () => {
    renderHook(() => useRagStatusPolling([], "token"));

    expect(getFolderRagStatus).not.toHaveBeenCalled();
  });

  it("does not fetch when token is null", () => {
    renderHook(() => useRagStatusPolling([1], null));

    expect(getFolderRagStatus).not.toHaveBeenCalled();
  });

  it("stops polling when folder is empty", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({ folder_id: 1, files: [] });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    renderHook(() => useRagStatusPolling([1], "token"));

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

    renderHook(() => useRagStatusPolling([1], "token"));

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

    renderHook(() => useRagStatusPolling([1], "token"));

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

    renderHook(() => useRagStatusPolling([1], "token"));

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

    const { unmount } = renderHook(() => useRagStatusPolling([1], "token"));

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

    const { result } = renderHook(() => useRagStatusPolling([1], "token"));

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toEqual({ status: "ready", error: null });
    });

    const callsBefore = vi.mocked(getFolderRagStatus).mock.calls.length;

    act(() => result.current.restart());

    await waitFor(() => {
      expect(vi.mocked(getFolderRagStatus).mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it("resets statuses when folderIds changes", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "a.pdf", rag_status: "ready", rag_error: null }],
    });

    const { result, rerender } = renderHook(
      ({ folderIds }: { folderIds: number[] }) => useRagStatusPolling(folderIds, "token"),
      { initialProps: { folderIds: [1] } },
    );

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toBeDefined();
    });

    vi.mocked(getFolderRagStatus).mockResolvedValue({ folder_id: 2, files: [] });

    rerender({ folderIds: [2] });

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toBeUndefined();
    });
  });

  it("merges statuses from multiple folders", async () => {
    vi.mocked(getFolderRagStatus).mockImplementation(async (folderId) => ({
      folder_id: folderId,
      files:
        folderId === 1
          ? [{ file_id: 10, name: "a.pdf", rag_status: "ready" as const, rag_error: null }]
          : [{ file_id: 20, name: "b.pdf", rag_status: "processing" as const, rag_error: null }],
    }));

    const { result } = renderHook(() => useRagStatusPolling([1, 2], "token"));

    await waitFor(() => {
      expect(result.current.ragStatuses[10]).toEqual({ status: "ready", error: null });
      expect(result.current.ragStatuses[20]).toEqual({ status: "processing", error: null });
    });
  });

  it("fetches all folders in parallel (one call per folder)", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({ folder_id: 1, files: [] });

    renderHook(() => useRagStatusPolling([1, 2, 3], "token"));

    await waitFor(() => {
      expect(vi.mocked(getFolderRagStatus).mock.calls.length).toBeGreaterThanOrEqual(3);
    });

    const calledIds = vi.mocked(getFolderRagStatus).mock.calls.map((c) => c[0]);
    expect(calledIds).toContain(1);
    expect(calledIds).toContain(2);
    expect(calledIds).toContain(3);
  });

  it("applies exponential backoff on fetch error", async () => {
    vi.mocked(getFolderRagStatus).mockRejectedValue(new Error("network error"));

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    renderHook(() => useRagStatusPolling([1], "token"));

    await waitFor(() => {
      const timeouts = setTimeoutSpy.mock.calls.map((c) => c[1] as number);
      // First retry should be at BASE_DELAY (5000); if it errors again, next is 10000
      expect(timeouts.some((t) => t >= 5000)).toBe(true);
    });
  });

  it("resets backoff delay to base after a successful fetch", async () => {
    vi.useFakeTimers();

    let callCount = 0;
    vi.mocked(getFolderRagStatus).mockImplementation(async () => {
      callCount++;
      if (callCount === 1) throw new Error("transient error");
      return {
        folder_id: 1,
        files: [{ file_id: 10, name: "a.pdf", rag_status: "processing" as const, rag_error: null }],
      };
    });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    renderHook(() => useRagStatusPolling([1], "token"));

    // Flush the initial async poll (fires immediately, not via timer)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // First poll errored → delay doubled to 10000; advance past it to trigger second poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10001);
    });

    // Second call should have fired and succeeded
    expect(callCount).toBeGreaterThanOrEqual(2);

    // After the successful fetch, the next scheduled timeout should be BASE_DELAY (5000), not 10000
    const timeouts = setTimeoutSpy.mock.calls.map((c) => c[1] as number);
    const lastTimeout = timeouts[timeouts.length - 1];
    expect(lastTimeout).toBe(5000);

    vi.useRealTimers();
  });
});
