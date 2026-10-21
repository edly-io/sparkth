import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { disconnectSlack } from "@/lib/slack";
import SlackConnectionCard from "@/plugins/slack/components/SlackConnectionCard";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/slack", () => ({
  getAuthorizationUrl: vi.fn(),
  disconnectSlack: vi.fn(),
}));

const CONNECTED = { connected: true, team_name: "Biology 101" };

async function confirmDisconnect() {
  const onStatusChange = vi.fn();
  const onError = vi.fn();
  render(
    <SlackConnectionCard status={CONNECTED} onStatusChange={onStatusChange} onError={onError} />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
  await userEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "Disconnect" }),
  );
  return { onStatusChange, onError };
}

describe("SlackConnectionCard disconnect", () => {
  beforeEach(() => {
    vi.mocked(disconnectSlack).mockReset();
  });

  it("disconnects after confirming", async () => {
    vi.mocked(disconnectSlack).mockResolvedValue(undefined);

    const { onStatusChange } = await confirmDisconnect();

    expect(disconnectSlack).toHaveBeenCalledWith("test-token");
    expect(onStatusChange).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the dialog open with an error when disconnecting fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(disconnectSlack).mockRejectedValue(new Error("boom"));

    const { onStatusChange } = await confirmDisconnect();

    expect(await screen.findByText("Failed to disconnect Slack.")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onStatusChange).not.toHaveBeenCalled();
  });
});
