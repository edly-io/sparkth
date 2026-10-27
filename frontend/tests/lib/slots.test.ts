import { describe, it, expect } from "vitest";

import {
  namedSlotItem,
  setNamedSlotItems,
  slotItems,
  type NamedSlot,
  type Slot,
} from "@/lib/slots";

interface Named {
  name: string;
  label: string;
}

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

describe("named slots", () => {
  it("finds an item by its name, and nothing for a name no plugin set", () => {
    const slot: NamedSlot<Named> = new Map();

    setNamedSlotItems(slot, "slack", [{ name: "slack", label: "Slack" }]);

    expect(namedSlotItem(slot, "slack")).toEqual({ name: "slack", label: "Slack" });
    expect(namedSlotItem(slot, "chat")).toBeUndefined();
  });

  it("lets a plugin set its items again, replacing the ones it set before", () => {
    const slot: NamedSlot<Named> = new Map();

    setNamedSlotItems(slot, "slack", [{ name: "slack", label: "first" }]);
    setNamedSlotItems(slot, "slack", [{ name: "slack", label: "second" }]);

    expect(slotItems(slot)).toEqual([["slack", { name: "slack", label: "second" }]]);
  });

  it("refuses a name another plugin already set, and keeps that plugin's item", () => {
    const slot: NamedSlot<Named> = new Map();
    setNamedSlotItems(slot, "slack", [{ name: "shared", label: "slack's" }]);

    expect(() => setNamedSlotItems(slot, "chat", [{ name: "shared", label: "chat's" }])).toThrow();
    expect(namedSlotItem(slot, "shared")).toEqual({ name: "shared", label: "slack's" });
  });
});
