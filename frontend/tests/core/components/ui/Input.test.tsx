import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, it, expect, vi, type MockInstance } from "vitest";

import { Input } from "@/core/components/ui/Input";

describe("Input", () => {
  it("is marked invalid and described by its error", () => {
    render(<Input id="name" label="Name" error="Name is required." />);

    const input = screen.getByLabelText("Name");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Name is required.");
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required.");
  });

  it("is not marked invalid without an error", () => {
    render(<Input id="name" label="Name" />);

    expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("Input noAutofill", () => {
  let consoleError: MockInstance<typeof console.error>;

  beforeEach(() => {
    consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  // React drops an unrecognised prop and logs once, so the log is the only trace of a leak.
  afterEach(() => {
    const errors = [...consoleError.mock.calls];
    consoleError.mockRestore();
    expect(errors).toEqual([]);
  });

  it("opts a text input out of browser and password-manager autofill", () => {
    render(<Input id="url" label="Url" noAutofill />);

    const input = screen.getByLabelText("Url");
    expect(input).toHaveAttribute("autocomplete", "off");
    expect(input).toHaveAttribute("data-1p-ignore");
    expect(input).toHaveAttribute("data-lpignore", "true");
    expect(input).toHaveAttribute("data-bwignore");
  });

  it("opts a password input out of autofill even when the caller sets autocomplete", () => {
    render(<Input id="key" label="Key" type="password" autoComplete="off" noAutofill />);

    const input = screen.getByLabelText("Key");
    expect(input).toHaveAttribute("autocomplete", "new-password");
    expect(input).toHaveAttribute("data-1p-ignore");
    expect(input).toHaveAttribute("data-lpignore", "true");
    expect(input).toHaveAttribute("data-bwignore");
  });

  it("leaves autofill to the browser by default", () => {
    render(<Input id="password" label="Password" type="password" />);

    const input = screen.getByLabelText("Password");
    expect(input).not.toHaveAttribute("autocomplete");
    expect(input).not.toHaveAttribute("data-1p-ignore");
    expect(input).not.toHaveAttribute("data-lpignore");
    expect(input).not.toHaveAttribute("data-bwignore");
  });
});
