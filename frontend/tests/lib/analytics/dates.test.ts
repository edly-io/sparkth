import { describe, it, expect } from "vitest";
import { addDays, daysInclusive, parseIsoDate, toIsoDate } from "@/lib/analytics";

describe("UTC date helpers", () => {
  it("takes the calendar date in UTC, not local time", () => {
    expect(toIsoDate(new Date("2026-07-24T23:30:00-05:00"))).toBe("2026-07-25");
  });

  it("adds days across month and year boundaries", () => {
    expect(addDays("2026-01-31", 1)).toBe("2026-02-01");
    expect(addDays("2026-01-01", -1)).toBe("2025-12-31");
  });

  it("counts days inclusively", () => {
    expect(daysInclusive("2026-07-01", "2026-07-01")).toBe(1);
    expect(daysInclusive("2025-12-31", "2026-01-02")).toBe(3);
  });

  it("parses strict ISO dates and rejects impossible or malformed ones", () => {
    expect(parseIsoDate("2026-02-28")?.toISOString()).toBe("2026-02-28T00:00:00.000Z");
    expect(parseIsoDate("2026-02-30")).toBeNull();
    expect(parseIsoDate("2026-2-3")).toBeNull();
    expect(parseIsoDate("")).toBeNull();
  });
});
