import { describe, it, expect } from "vitest";

import { configString, stringConfigOf } from "@/lib/plugins/config";

describe("configString", () => {
  it("returns a string value as-is", () => {
    expect(configString({ bot_name: "Sparkth" }, "bot_name")).toBe("Sparkth");
  });

  it("returns undefined for a missing key", () => {
    expect(configString({}, "bot_name")).toBeUndefined();
  });

  it("returns undefined for a non-string value rather than coercing it", () => {
    expect(configString({ allowed_sources: ["a"] }, "allowed_sources")).toBeUndefined();
    expect(configString({ llm_temperature: 0.7 }, "llm_temperature")).toBeUndefined();
    expect(configString({ bot_name: null }, "bot_name")).toBeUndefined();
  });

  it("preserves the empty string, which callers treat as 'unset'", () => {
    expect(configString({ llm_config_id: "" }, "llm_config_id")).toBe("");
  });
});

describe("stringConfigOf", () => {
  it("keeps string entries unchanged", () => {
    expect(stringConfigOf({ a: "1", b: "two" })).toEqual({ a: "1", b: "two" });
  });

  it("JSON-encodes non-string entries so no field is dropped from an editor", () => {
    expect(stringConfigOf({ sources: ["a", "b"], count: 2, on: true })).toEqual({
      sources: '["a","b"]',
      count: "2",
      on: "true",
    });
  });

  it("renders null and undefined as empty strings", () => {
    expect(stringConfigOf({ a: null, b: undefined })).toEqual({ a: "", b: "" });
  });

  it("returns an empty object for an absent config", () => {
    expect(stringConfigOf(undefined)).toEqual({});
  });
});
