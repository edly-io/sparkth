import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { disconnectSlack } from "@/lib/slack";
import SlackConnectionCard from "@/plugins/slack/components/SlackConnectionCard";

const auth = vi.hoisted(() => ({ token: "test-token" as string | null }));
vi.mock("@/lib/auth/hooks", () => ({
  useAuth: () => ({ token: auth.token }),
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
    auth.token = "test-token";
  });

  it("disconnects after confirming", async () => {
    vi.mocked(disconnectSlack).mockResolvedValue(undefined);

    const { onStatusChange } = await confirmDisconnect();

    expect(disconnectSlack).toHaveBeenCalledWith("test-token");
    expect(onStatusChange).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the dialog open with the reason when disconnecting fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(disconnectSlack).mockRejectedValue(
      new ApiRequestError({ message: "Slack workspace not connected", fieldErrors: {} }, 404),
    );

    const { onStatusChange } = await confirmDisconnect();

    expect(await screen.findByText("Slack workspace not connected")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onStatusChange).not.toHaveBeenCalled();
  });

  it("keeps the dialog open with an error when signed out", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    auth.token = null;

    const { onStatusChange } = await confirmDisconnect();

    expect(await screen.findByText("Failed to disconnect Slack.")).toBeInTheDocument();
    expect(disconnectSlack).not.toHaveBeenCalled();
    expect(onStatusChange).not.toHaveBeenCalled();
  });
});
