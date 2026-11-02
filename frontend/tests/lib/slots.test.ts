import { describe, it, expect } from "vitest";

import { slotItems, type Slot } from "@/lib/slots";

describe("slots", () => {
  it("returns each item with its plugin, by plugin name and then in the order the plugin set them", () => {
    const slot: Slot<string> = new Map();

    slot.set("slack", ["slack item"]);
    slot.set("chat", ["first", "second"]);

    expect(slotItems(slot)).toEqual([
      ["chat", "first"],
      ["chat", "second"],
      ["slack", "slack item"],
    ]);
  });
});
