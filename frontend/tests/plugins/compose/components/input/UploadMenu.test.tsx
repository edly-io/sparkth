import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { UploadMenu } from "@/plugins/compose/src/components/ui/input/UploadMenu";
import { ATTACHMENT_SOURCES, type AttachmentSource } from "@/plugins/compose/lib";

// usePlugin is mocked to read this directly, so a test sets it before rendering.
let enabledPlugins = new Set<string>();

vi.mock("@/lib/plugins/context", () => ({
  usePlugin: (name: string) => ({
    isEnabled: enabledPlugins.has(name),
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
  render(<UploadMenu onClose={onClose} onUploadText={vi.fn()} onPickSource={onPickSource} />);
  return { onClose, onPickSource };
}

const filesSource: AttachmentSource = {
  label: "Pick from Files",
  icon: FilesIcon,
  loadPicker: () => Promise.resolve({ default: () => null }),
};

describe("UploadMenu", () => {
  beforeEach(() => {
    ATTACHMENT_SOURCES.clear();
    ATTACHMENT_SOURCES.set("files-plugin", [filesSource]);
    enabledPlugins = new Set(["files-plugin"]);
  });

  it("lists a source set in the slot, with its label and icon, while its plugin is enabled", () => {
    renderMenu();

    expect(screen.getByRole("button", { name: "Pick from Files" })).toBeInTheDocument();
    expect(screen.getByTestId("files-icon")).toBeInTheDocument();
  });

  it("hides a source while its plugin is disabled", () => {
    enabledPlugins = new Set();
    renderMenu();

    expect(screen.queryByRole("button", { name: "Pick from Files" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select File" })).toBeInTheDocument();
  });

  it("opens the chosen source and closes the menu", async () => {
    const { onClose, onPickSource } = renderMenu();

    await userEvent.click(screen.getByRole("button", { name: "Pick from Files" }));

    expect(onPickSource).toHaveBeenCalledWith(filesSource);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
