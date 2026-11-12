import { describe, it, expect } from "vitest";
import {
  answeredOptions,
  appendLine,
  replaceLine,
  splitOptionsBlock,
} from "@/plugins/compose/src/components/ui/messages/optionsBlock";

describe("splitOptionsBlock", () => {
  it("splits a trailing options block off the body", () => {
    const content = "Who is it for?\n\n```options\nBeginners\nProfessionals\n```";
    expect(splitOptionsBlock(content)).toEqual({
      body: "Who is it for?",
      options: ["Beginners", "Professionals"],
      closed: true,
      single: false,
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
      single: false,
    });
  });

  it("ignores a block followed by text", () => {
    const content = "Q?\n```options\nA\n```\nMore prose.";
    expect(splitOptionsBlock(content)).toEqual({
      body: content,
      options: null,
      closed: false,
      single: false,
    });
  });

  it("ignores fences of another language", () => {
    const content = "Code:\n```python\nprint(1)\n```";
    expect(splitOptionsBlock(content)).toEqual({
      body: content,
      options: null,
      closed: false,
      single: false,
    });
  });

  it("drops empty lines, surrounding whitespace and duplicates", () => {
    const content = "Q?\n```options\n  A \n\nB\nA\n```";
    expect(splitOptionsBlock(content).options).toEqual(["A", "B"]);
  });

  it("returns null options for a block with no option lines", () => {
    const content = "Q?\n```options\n\n```";
    expect(splitOptionsBlock(content)).toEqual({
      body: content,
      options: null,
      closed: false,
      single: false,
    });
  });

  it("returns the content unchanged when there is no block", () => {
    expect(splitOptionsBlock("Plain reply.")).toEqual({
      body: "Plain reply.",
      options: null,
      closed: false,
      single: false,
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

describe("splitOptionsBlock — single choice", () => {
  it("marks an `options single` block as single-choice", () => {
    expect(splitOptionsBlock("One or two?\n```options single\nOne\nTwo\n```")).toEqual({
      body: "One or two?",
      options: ["One", "Two"],
      closed: true,
      single: true,
    });
  });

  it("recognises an unclosed single block while it streams in", () => {
    const split = splitOptionsBlock("Q?\n```options single\nA");
    expect(split.options).toEqual(["A"]);
    expect(split.single).toBe(true);
    expect(split.closed).toBe(false);
  });

  it("ignores a fence whose info string only starts with single", () => {
    expect(splitOptionsBlock("Q?\n```options singles\nA\n```").options).toBeNull();
  });
});

describe("replaceLine", () => {
  it("swaps a line for another", () => {
    expect(replaceLine("Intro\nOne", "One", "Two")).toBe("Intro\nTwo");
  });

  it("just appends when the removed line is absent", () => {
    expect(replaceLine("Intro", "One", "Two")).toBe("Intro\nTwo");
  });

  it("keeps the other lines", () => {
    expect(replaceLine("A\nOne\nB", "One", "Two")).toBe("A\nB\nTwo");
  });
});
