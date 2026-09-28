import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { OptionsPrompt } from "@/plugins/chat/components/messages/OptionsPrompt";
import chatEn from "@/plugins/chat/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

const OPTIONS = ["Beginners", "Professionals", "Students"];
const onRespond = vi.fn();

function renderPrompt(interactive = true, selected: string[] = []) {
  return renderWithIntl(
    <OptionsPrompt
      options={OPTIONS}
      interactive={interactive}
      selected={selected}
      onRespond={onRespond}
    />,
    { chat: chatEn.chat },
  );
}

describe("OptionsPrompt — interactive", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a checkbox per option", () => {
    renderPrompt();
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
    expect(screen.getByLabelText("Professionals")).toBeInTheDocument();
  });

  it("names the free-text input for assistive technology", () => {
    renderPrompt();
    expect(screen.getByRole("textbox", { name: "Add something else…" })).toBeInTheDocument();
  });

  it("disables Respond until something is chosen", () => {
    renderPrompt();
    expect(screen.getByRole("button", { name: "Respond" })).toBeDisabled();
  });

  it("sends the checked options in display order", async () => {
    renderPrompt();
    await userEvent.click(screen.getByLabelText("Students"));
    await userEvent.click(screen.getByLabelText("Beginners"));
    await userEvent.click(screen.getByRole("button", { name: "Respond" }));
    expect(onRespond).toHaveBeenCalledWith("Beginners\nStudents");
  });

  it("does not send an option that was checked then unchecked", async () => {
    renderPrompt();
    await userEvent.click(screen.getByLabelText("Beginners"));
    await userEvent.click(screen.getByLabelText("Beginners"));
    await userEvent.click(screen.getByLabelText("Students"));
    await userEvent.click(screen.getByRole("button", { name: "Respond" }));
    expect(onRespond).toHaveBeenCalledWith("Students");
  });

  it("appends the typed text after the checked options", async () => {
    renderPrompt();
    await userEvent.click(screen.getByLabelText("Beginners"));
    await userEvent.type(screen.getByPlaceholderText("Add something else…"), "  Retirees ");
    await userEvent.click(screen.getByRole("button", { name: "Respond" }));
    expect(onRespond).toHaveBeenCalledWith("Beginners\nRetirees");
  });

  it("sends typed text alone when nothing is checked, on Enter", async () => {
    renderPrompt();
    await userEvent.type(screen.getByPlaceholderText("Add something else…"), "Retirees{Enter}");
    expect(onRespond).toHaveBeenCalledWith("Retirees");
  });

  it("Enter with nothing chosen sends nothing", async () => {
    renderPrompt();
    await userEvent.type(screen.getByPlaceholderText("Add something else…"), "   {Enter}");
    expect(onRespond).not.toHaveBeenCalled();
  });

  it("keeps the sent options checked and locks them", async () => {
    renderPrompt();
    await userEvent.click(screen.getByLabelText("Students"));
    await userEvent.click(screen.getByRole("button", { name: "Respond" }));
    expect(screen.getByLabelText("Students")).toBeChecked();
    expect(screen.getByLabelText("Students")).toBeDisabled();
    expect(screen.getByLabelText("Beginners")).not.toBeChecked();
  });

  it("sends once on a double click", async () => {
    renderPrompt();
    await userEvent.click(screen.getByLabelText("Beginners"));
    await userEvent.dblClick(screen.getByRole("button", { name: "Respond" }));
    expect(onRespond).toHaveBeenCalledOnce();
  });
});

describe("OptionsPrompt — read-only", () => {
  it("renders disabled, unchecked checkboxes and no input or button", () => {
    renderPrompt(false);
    for (const box of screen.getAllByRole("checkbox")) {
      expect(box).toBeDisabled();
      expect(box).not.toBeChecked();
    }
    expect(screen.queryByRole("button", { name: "Respond" })).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Add something else…")).not.toBeInTheDocument();
  });
});

describe("OptionsPrompt — answered", () => {
  it("shows the selected options checked and disabled", () => {
    renderPrompt(false, ["Professionals"]);
    expect(screen.getByLabelText("Professionals")).toBeChecked();
    expect(screen.getByLabelText("Professionals")).toBeDisabled();
    expect(screen.getByLabelText("Beginners")).not.toBeChecked();
  });
});
