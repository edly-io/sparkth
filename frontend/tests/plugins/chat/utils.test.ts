import { describe, it, expect } from "vitest";

import { truncate } from "@/plugins/chat/utils";

describe("truncate", () => {
  it("returns text at or under the limit unchanged", () => {
    expect(truncate("abc", 3)).toBe("abc");
    expect(truncate("ab", 3)).toBe("ab");
  });

  it("cuts longer text to the limit, ending in an ellipsis", () => {
    const result = truncate("abcdef", 4);
    expect(result).toBe("abc…");
    expect(result).toHaveLength(4);
  });
});
