import { describe, it, expect } from "vitest";
import {
  answeredOptions,
  appendLine,
  splitOptionsBlock,
} from "@/plugins/chat/components/messages/optionsBlock";

describe("splitOptionsBlock", () => {
  it("splits a trailing options block off the body", () => {
    const content = "Who is it for?\n\n```options\nBeginners\nProfessionals\n```";
    expect(splitOptionsBlock(content)).toEqual({
      body: "Who is it for?",
      options: ["Beginners", "Professionals"],
      closed: true,
    });
  });

  it("accepts trailing whitespace after the closing fence", () => {
    const content = "Q?\n```options\nA\n```\n\n  ";
    expect(splitOptionsBlock(content).options).toEqual(["A"]);
  });

  it("treats an unclosed block as the trailing block", () => {
    expect(splitOptionsBlock("Q?\n```options\nA\nB")).toEqual({
      body: "Q?",
      options: ["A", "B"],
      closed: false,
    });
  });

  it("ignores a block followed by text", () => {
    const content = "Q?\n```options\nA\n```\nMore prose.";
    expect(splitOptionsBlock(content)).toEqual({ body: content, options: null, closed: false });
  });

  it("ignores fences of another language", () => {
    const content = "Code:\n```python\nprint(1)\n```";
    expect(splitOptionsBlock(content)).toEqual({ body: content, options: null, closed: false });
  });

  it("drops empty lines, surrounding whitespace and duplicates", () => {
    const content = "Q?\n```options\n  A \n\nB\nA\n```";
    expect(splitOptionsBlock(content).options).toEqual(["A", "B"]);
  });

  it("returns null options for a block with no option lines", () => {
    const content = "Q?\n```options\n\n```";
    expect(splitOptionsBlock(content)).toEqual({ body: content, options: null, closed: false });
  });

  it("returns the content unchanged when there is no block", () => {
    expect(splitOptionsBlock("Plain reply.")).toEqual({
      body: "Plain reply.",
      options: null,
      closed: false,
    });
  });
});

describe("answeredOptions", () => {
  const options = ["Beginners", "Professionals", "Students"];

  it("returns the options that appear as lines of the reply, in display order", () => {
    expect(answeredOptions(options, "Students\nBeginners\nRetirees")).toEqual([
      "Beginners",
      "Students",
    ]);
  });

  it("ignores surrounding whitespace on reply lines", () => {
    expect(answeredOptions(options, "  Professionals ")).toEqual(["Professionals"]);
  });

  it("does not match an option that only appears inside a longer line", () => {
    expect(answeredOptions(options, "Not Beginners")).toEqual([]);
  });
});

describe("appendLine", () => {
  it("returns the line for a blank message", () => {
    expect(appendLine("  \n", "Beginners")).toBe("Beginners");
  });

  it("appends on a new line after existing text", () => {
    expect(appendLine("For my team", "Beginners")).toBe("For my team\nBeginners");
  });

  it("trims trailing whitespace before appending", () => {
    expect(appendLine("Beginners\n\n", "Students")).toBe("Beginners\nStudents");
  });

  it("leaves the message unchanged when the line is already there", () => {
    expect(appendLine("For my team\n  Beginners \n", "Beginners")).toBe(
      "For my team\n  Beginners \n",
    );
  });
});
