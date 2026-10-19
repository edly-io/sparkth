import { describe, expect, it } from "vitest";
import { documentTotals, type DriveDocumentsPoint } from "@/lib/analytics";

// The server marks these ready; the rows below follow it.
const READY = new Set(["ingested", "duplicate"]);
const row = (
  outcome: string | null,
  document_count: number,
  seconds_total = 0,
  ready = READY.has(outcome ?? ""),
): DriveDocumentsPoint => ({
  bucket: "2026-07-23",
  outcome,
  ready,
  document_count,
  seconds_total,
});

describe("documentTotals", () => {
  it("splits ready from not-ready and averages time over ready only", () => {
    const totals = documentTotals([
      row("ingested", 3, 60),
      row("duplicate", 1, 4),
      row("scanned_pdf", 2, 100),
      row("drive_error", 1, 9),
      row("scanned_pdf", 1, 1),
    ]);
    expect(totals.total).toBe(8);
    expect(totals.ready).toBe(4);
    expect(totals.avgSecondsToReady).toBe(16);
    expect(totals.notReady).toEqual([
      { outcome: "scanned_pdf", count: 3 },
      { outcome: "drive_error", count: 1 },
    ]);
  });

  it("follows the server's ready flag, even for an outcome it doesn't know", () => {
    const totals = documentTotals([row("new_outcome", 2, 10, true), row("ingested", 1, 5, false)]);
    expect(totals.ready).toBe(2);
    expect(totals.avgSecondsToReady).toBe(5);
    expect(totals.notReady).toEqual([{ outcome: "ingested", count: 1 }]);
  });

  it("has no average when nothing became ready", () => {
    expect(documentTotals([row("failed", 2, 8)]).avgSecondsToReady).toBeNull();
    expect(documentTotals([]).total).toBe(0);
  });
});
