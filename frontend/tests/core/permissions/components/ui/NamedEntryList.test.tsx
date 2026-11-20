import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";

const auth = vi.hoisted(() => ({ token: "test-token" as string | null }));
vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: auth.token }) }));

import { NamedEntryList } from "@/core/permissions/components/ui/NamedEntryList";

const load = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  auth.token = "test-token";
  vi.spyOn(console, "error").mockImplementation(() => {});
});

function renderList() {
  renderWithIntl(
    <NamedEntryList label="Roles" load={load} empty="No roles yet." loadFailed="Couldn't load." />,
  );
}

describe("NamedEntryList", () => {
  it("lists each entry's name and description in the order loaded", async () => {
    load.mockResolvedValue([
      { id: 1, name: "admin", description: "Everything" },
      { id: 2, name: "viewer", description: null },
    ]);
    renderList();

    const list = await screen.findByRole("list", { name: "Roles" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("admin");
    expect(items[0]).toHaveTextContent("Everything");
    expect(items[1]).toHaveTextContent("viewer");
    expect(load).toHaveBeenCalledWith("test-token");
  });

  it("says so when there are no entries", async () => {
    load.mockResolvedValue([]);
    renderList();

    expect(await screen.findByText("No roles yet.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("shows an error when loading fails", async () => {
    load.mockRejectedValue(new Error("boom"));
    renderList();

    expect(await screen.findByText("Couldn't load.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("waits for a token before loading", () => {
    auth.token = null;
    renderList();

    expect(load).not.toHaveBeenCalled();
  });
});
