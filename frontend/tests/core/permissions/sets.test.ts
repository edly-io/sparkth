import { describe, it, expect } from "vitest";
import { toggleItem } from "@/core/permissions/sets";

describe("toggleItem", () => {
  it("adds an item the set doesn't have", () => {
    expect(toggleItem(new Set(["a"]), "b")).toEqual(new Set(["a", "b"]));
  });

  it("removes an item the set has", () => {
    expect(toggleItem(new Set(["a", "b"]), "a")).toEqual(new Set(["b"]));
  });

  it("leaves the set it was given as it was", () => {
    const set = new Set(["a"]);

    toggleItem(set, "a");

    expect(set).toEqual(new Set(["a"]));
  });
});
