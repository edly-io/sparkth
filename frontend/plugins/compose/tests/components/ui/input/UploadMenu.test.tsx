import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { UploadMenu } from "@/plugins/compose/src/components/ui/input/UploadMenu";
import { ATTACHMENT_SOURCES, type AttachmentSource } from "@/plugins/compose/lib";
import composeEn from "@/plugins/compose/src/i18n/en.json";
import { renderWithIntl } from "@/lib/testing/intl";

// usePlugin is mocked to read this directly, so a test sets it before rendering.
let usablePlugins = new Set<string>();

vi.mock("@/lib/plugins/context", () => ({
  usePlugin: (name: string) => ({
    isUsable: usablePlugins.has(name),
    loading: false,
    config: {},
  }),
}));

function FilesIcon({ className }: { className?: string }) {
  return <svg data-testid="files-icon" className={className} />;
}

function renderMenu() {
  const onClose = vi.fn();
  const onPickSource = vi.fn();
  const onUploadFromComputer = vi.fn();
  const { container } = renderWithIntl(
    <UploadMenu
      onClose={onClose}
      onUploadFromComputer={onUploadFromComputer}
      onPickSource={onPickSource}
    />,
    composeEn,
  );
  const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]')!;
  return { onClose, onPickSource, onUploadFromComputer, fileInput };
}

const filesSource: AttachmentSource = {
  id: "files-source",
  label: "Pick from Files",
  icon: FilesIcon,
  loadPicker: () => Promise.resolve({ default: () => null }),
};

describe("UploadMenu", () => {
  beforeEach(() => {
    ATTACHMENT_SOURCES.clear();
    ATTACHMENT_SOURCES.set("files-plugin", [filesSource]);
    usablePlugins = new Set(["files-plugin"]);
  });

  it("lists a source set in the slot, with its label and icon, while its plugin is usable", () => {
    renderMenu();

    expect(screen.getByRole("button", { name: "Pick from Files" })).toBeInTheDocument();
    expect(screen.getByTestId("files-icon")).toBeInTheDocument();
  });

  it("hides a source while its plugin is disabled", () => {
    usablePlugins = new Set();
    renderMenu();

    expect(screen.queryByRole("button", { name: "Pick from Files" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Select files/ })).toBeInTheDocument();
  });

  it("opens the chosen source and closes the menu", async () => {
    const { onClose, onPickSource } = renderMenu();

    await userEvent.click(screen.getByRole("button", { name: "Pick from Files" }));

    expect(onPickSource).toHaveBeenCalledWith(filesSource);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("uploads every file picked from the computer and closes the menu", async () => {
    const { onClose, onUploadFromComputer, fileInput } = renderMenu();
    const files = [new File(["Week 1"], "notes.txt"), new File(["Week 2"], "outline.pdf")];

    await userEvent.upload(fileInput, files);

    expect(onUploadFromComputer).toHaveBeenCalledWith(files);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("says which files can be picked from the computer, and how much in total", () => {
    renderMenu();

    expect(screen.getByText(".txt or .pdf, up to 3 MB in total")).toBeInTheDocument();
  });
});
