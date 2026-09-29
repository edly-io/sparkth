import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { OptionsPrompt } from "@/plugins/chat/components/messages/OptionsPrompt";
import chatEn from "@/plugins/chat/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

const OPTIONS = ["Beginners", "Professionals", "Students"];
const onOptionCheck = vi.fn();
const TYPE_ELSE = chatEn.chat.optionsTypeElse;
const NONE_SELECTED = chatEn.chat.optionsNoneSelected;

function renderPrompt(interactive = true, selected: string[] = [], answered = false) {
  return renderWithIntl(
    <OptionsPrompt
      options={OPTIONS}
      interactive={interactive}
      selected={selected}
      answered={answered}
      onOptionCheck={onOptionCheck}
    />,
    { chat: chatEn.chat },
  );
}

describe("OptionsPrompt — interactive", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a checkbox per option and the type-anything-else note", () => {
    renderPrompt();
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
    expect(screen.getByText(TYPE_ELSE)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("calls onOptionCheck with the option when a box is checked", async () => {
    renderPrompt();
    await userEvent.click(screen.getByLabelText("Students"));
    expect(onOptionCheck).toHaveBeenCalledWith("Students");
    expect(screen.getByLabelText("Students")).toBeChecked();
  });

  it("calls onOptionCheck only when a box becomes checked", async () => {
    renderPrompt();
    await userEvent.click(screen.getByLabelText("Students"));
    await userEvent.click(screen.getByLabelText("Students"));
    expect(onOptionCheck).toHaveBeenCalledOnce();
    expect(screen.getByLabelText("Students")).not.toBeChecked();
  });
});

describe("OptionsPrompt — read-only", () => {
  it("renders disabled checkboxes and no note while unanswered", () => {
    renderPrompt(false);
    for (const box of screen.getAllByRole("checkbox")) {
      expect(box).toBeDisabled();
      expect(box).not.toBeChecked();
    }
    expect(screen.queryByText(TYPE_ELSE)).not.toBeInTheDocument();
    expect(screen.queryByText(NONE_SELECTED)).not.toBeInTheDocument();
  });

  it("shows the selected options checked when answered", () => {
    renderPrompt(false, ["Professionals"], true);
    expect(screen.getByLabelText("Professionals")).toBeChecked();
    expect(screen.getByLabelText("Beginners")).not.toBeChecked();
    expect(screen.queryByText(NONE_SELECTED)).not.toBeInTheDocument();
  });

  it("says no option was selected when the answer matches none", () => {
    renderPrompt(false, [], true);
    expect(screen.getByText(NONE_SELECTED)).toBeInTheDocument();
  });
});
