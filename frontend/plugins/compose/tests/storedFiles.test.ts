import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  addStoredFiles,
  clearStoredFiles,
  getStoredFiles,
  isWithinStorageLimit,
} from "@/plugins/compose/src/storedFiles";

const notes = { name: "notes.txt", size: 5, text: "mitochondria" };
const syllabus = { name: "syllabus.txt", size: 12, text: "Week 1: cells" };

const quotaExceeded = () => new DOMException("Storage is full.", "QuotaExceededError");

describe("storedFiles", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("has no files for a conversation it never kept any for", () => {
    expect(getStoredFiles(7, "conv-1")).toEqual([]);
  });

  it("adds files to the ones already kept", () => {
    addStoredFiles(7, "conv-1", [notes]);
    addStoredFiles(7, "conv-1", [syllabus]);

    expect(getStoredFiles(7, "conv-1")).toEqual([notes, syllabus]);
  });

  it("keeps each user's files apart", () => {
    addStoredFiles(7, "conv-1", [notes]);

    expect(getStoredFiles(8, "conv-1")).toEqual([]);
  });

  it("gives up the files added longest ago when storage is full", () => {
    vi.spyOn(Date, "now").mockReturnValueOnce(1).mockReturnValueOnce(2).mockReturnValue(3);
    addStoredFiles(7, "conv-old", [notes]);
    addStoredFiles(7, "conv-recent", [notes]);
    vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(() => {
      throw quotaExceeded();
    });

    addStoredFiles(7, "conv-1", [syllabus]);

    expect(getStoredFiles(7, "conv-1")).toEqual([syllabus]);
    expect(getStoredFiles(7, "conv-old")).toEqual([]);
    expect(getStoredFiles(7, "conv-recent")).toEqual([notes]);
  });

  it("doesn't keep files that don't fit even with nothing else kept", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw quotaExceeded();
    });

    expect(() => addStoredFiles(7, "conv-1", [syllabus])).not.toThrow();
    expect(getStoredFiles(7, "conv-1")).toEqual([]);
  });

  it("has no files when the kept entry can't be read", () => {
    localStorage.setItem("compose.files.7.conv-1", "not json");

    expect(getStoredFiles(7, "conv-1")).toEqual([]);
  });

  it("has no files, and keeps none, when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("Blocked.", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Blocked.", "SecurityError");
    });

    expect(() => addStoredFiles(7, "conv-1", [syllabus])).not.toThrow();
    expect(getStoredFiles(7, "conv-1")).toEqual([]);
  });

  it("finds text that fits within the storage limit, and leaves nothing behind checking", () => {
    expect(isWithinStorageLimit("Week 1: cells")).toBe(true);
    expect(localStorage.length).toBe(0);
  });

  it("finds text over the storage limit even with nothing else kept", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw quotaExceeded();
    });

    expect(isWithinStorageLimit("Week 1: cells")).toBe(false);
  });

  it("clears every user's files, and nothing else, from this browser", () => {
    addStoredFiles(7, "conv-1", [notes]);
    addStoredFiles(8, "conv-2", [syllabus]);
    localStorage.setItem("access_token", "token");

    clearStoredFiles();

    expect(getStoredFiles(7, "conv-1")).toEqual([]);
    expect(getStoredFiles(8, "conv-2")).toEqual([]);
    expect(localStorage.getItem("access_token")).toBe("token");
  });
});
