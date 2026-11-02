import { describe, it, expect } from "vitest";

import { validateLLMConfigName } from "@/core/llm/validation";

describe("validateLLMConfigName", () => {
  it("accepts letters, numbers, hyphens and underscores", () => {
    expect(validateLLMConfigName("my-key_2")).toBe("");
  });

  it("requires a name", () => {
    expect(validateLLMConfigName("   ")).toBe("Name is required");
  });

  it("rejects any other character", () => {
    expect(validateLLMConfigName("my key")).toBe(
      "Only letters, numbers, hyphens, and underscores allowed",
    );
  });

  it("rejects names longer than 100 characters", () => {
    expect(validateLLMConfigName("a".repeat(100))).toBe("");
    expect(validateLLMConfigName("a".repeat(101))).toBe("Name must be 100 characters or less");
  });
});
