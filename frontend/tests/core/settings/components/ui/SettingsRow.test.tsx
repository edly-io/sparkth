import { describe, it, expect, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { SettingsRow } from "@/core/settings/components/ui/SettingsRow";
import { renderWithIntl } from "@/tests/intl";

function renderRow(props: Partial<Parameters<typeof SettingsRow>[0]> = {}) {
  const onToggle = vi.fn(async () => {});
  renderWithIntl(
    <SettingsRow
      name="Canvas"
      active
      statusLabel="Enabled"
      toggleLabel="Turn Canvas on or off"
      onToggle={onToggle}
      toggleErrorMessage={(_, checked) => (checked ? "Failed to enable." : "Failed to disable.")}
      actions={<button aria-label="Configure Canvas">c</button>}
      {...props}
    />,
  );
  return onToggle;
}

describe("SettingsRow", () => {
  it("labels its switch and its actions", () => {
    renderRow();
    expect(screen.getByRole("switch", { name: "Turn Canvas on or off" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Configure Canvas" })).toBeDefined();
  });

  it("puts its switch after its actions, so every row's switch lines up", () => {
    renderRow();
    const action = screen.getByRole("button", { name: "Configure Canvas" });
    const toggle = screen.getByRole("switch");

    expect(action.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("says whether the row is active", () => {
    renderRow({ active: false, statusLabel: "Disabled" });
    expect(screen.getByText("Disabled")).toBeDefined();
  });

  it("puts the switch where `active` says and keeps it enabled by default", () => {
    renderRow({ active: false });
    const toggle = screen.getByRole("switch");
    expect(toggle).not.toBeChecked();
    expect(toggle).not.toBeDisabled();
  });

  it("lets the switch position and its disabled state differ from `active`", () => {
    renderRow({ active: false, toggleChecked: true, toggleDisabled: true });
    const toggle = screen.getByRole("switch");
    expect(toggle).toBeChecked();
    expect(toggle).toBeDisabled();
  });

  it("does not report a click on a disabled switch", () => {
    const onToggle = renderRow({ toggleDisabled: true });
    fireEvent.click(screen.getByRole("switch"));
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("reports a toggle", () => {
    const onToggle = renderRow();
    fireEvent.click(screen.getByRole("switch"));
    expect(onToggle).toHaveBeenCalledWith(false);
  });

  it("disables the switch until the toggle settles", async () => {
    let settle = () => {};
    renderRow({ onToggle: () => new Promise<void>((resolve) => (settle = resolve)) });

    fireEvent.click(screen.getByRole("switch"));
    expect(screen.getByRole("switch")).toBeDisabled();

    settle();
    await waitFor(() => expect(screen.getByRole("switch")).not.toBeDisabled());
  });

  it("shows a failed toggle inside the row, worded by the page", async () => {
    renderRow({ onToggle: async () => Promise.reject(new Error("boom")) });

    fireEvent.click(screen.getByRole("switch"));

    await waitFor(() =>
      expect(screen.getByRole("listitem").textContent).toContain("Failed to disable."),
    );
  });
});
