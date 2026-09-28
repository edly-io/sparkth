import { describe, it, expect } from "vitest";
import { splitOptionsBlock } from "@/plugins/chat/components/messages/optionsBlock";

describe("splitOptionsBlock", () => {
  it("splits a trailing options block off the body", () => {
    const content = "Who is it for?\n\n```options\nBeginners\nProfessionals\n```";
    expect(splitOptionsBlock(content)).toEqual({
      body: "Who is it for?",
      options: ["Beginners", "Professionals"],
    });
  });

  it("accepts trailing whitespace after the closing fence", () => {
    const content = "Q?\n```options\nA\n```\n\n  ";
    expect(splitOptionsBlock(content).options).toEqual(["A"]);
  });

  it("treats an unclosed block as the trailing block", () => {
    expect(splitOptionsBlock("Q?\n```options\nA\nB")).toEqual({ body: "Q?", options: ["A", "B"] });
  });

  it("ignores a block followed by text", () => {
    const content = "Q?\n```options\nA\n```\nMore prose.";
    expect(splitOptionsBlock(content)).toEqual({ body: content, options: null });
  });

  it("ignores fences of another language", () => {
    const content = "Code:\n```python\nprint(1)\n```";
    expect(splitOptionsBlock(content)).toEqual({ body: content, options: null });
  });

  it("drops empty lines, surrounding whitespace and duplicates", () => {
    const content = "Q?\n```options\n  A \n\nB\nA\n```";
    expect(splitOptionsBlock(content).options).toEqual(["A", "B"]);
  });

  it("returns null options for a block with no option lines", () => {
    const content = "Q?\n```options\n\n```";
    expect(splitOptionsBlock(content)).toEqual({ body: content, options: null });
  });

  it("returns the content unchanged when there is no block", () => {
    expect(splitOptionsBlock("Plain reply.")).toEqual({ body: "Plain reply.", options: null });
  });
});
