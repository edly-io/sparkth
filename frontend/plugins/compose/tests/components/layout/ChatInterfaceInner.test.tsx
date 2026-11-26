import { act, fireEvent, screen } from "@testing-library/react";
import { render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import ChatInterfaceInner from "@/plugins/compose/src/components/layout/ChatInterfaceInner";
import composeEn from "@/plugins/compose/src/i18n/en.json";
import type { ConversationLoadError } from "@/plugins/compose/src/types";
import { IntlTestProvider } from "@/lib/testing/intl";
import { fetchLLMConfigs } from "@/lib/llm/client";

// usePlugin is mocked to read this directly, so a test sets it before rendering.
let pluginConfig: Record<string, unknown> = {};
// useConversation is mocked to read this directly, so a test sets it before rendering.
let loadError: ConversationLoadError | null = null;

vi.mock("@/lib/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/plugins/context", () => ({
  usePlugin: () => ({ isUsable: false, loading: false, config: pluginConfig }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

// The message box's text is real state, so typing and option checks reach the input.
vi.mock("@/plugins/compose/src/hooks/useConversation", async () => {
  const { useState } = await import("react");
  return {
    useConversation: () => {
      const [inputMessage, setInputMessage] = useState("");
      return {
        loading: false,
        messages: [],
        loadError,
        error: null,
        setError: vi.fn(),
        inputMessage,
        setInputMessage,
        inputAttachments: [],
        setInputAttachments: vi.fn(),
        setMessages: vi.fn(),
        clearError: vi.fn(),
        skipNextLoadRef: { current: false },
      };
    },
  };
});

const mockHandleSend = vi.fn();
// Whether the mocked stream reports a turn still running in the open conversation.
let turnLive = false;
vi.mock("@/plugins/compose/src/hooks/useChatStream", () => ({
  useChatStream: () => ({
    handleSend: mockHandleSend,
    stopGeneration: vi.fn(),
    isStopping: false,
    isTurnLive: () => turnLive,
  }),
}));

vi.mock("@/lib/llm/client", () => ({
  fetchLLMConfigs: vi.fn(),
}));

// ChatMessages renders no widget for an empty message list (the mocked useConversation above
// always returns []), so the option-check path is reached through this stub instead.
vi.mock("@/plugins/compose/src/components/ui/messages/ChatMessages", () => ({
  ChatMessages: ({ onOptionCheck }: { onOptionCheck: (option: string) => void }) => (
    <button onClick={() => onOptionCheck("Beginners")}>Option</button>
  ),
}));

const mockedFetchLLMConfigs = vi.mocked(fetchLLMConfigs);

// jsdom has no scrollIntoView implementation; ChatMessages calls it on mount.
Element.prototype.scrollIntoView = vi.fn();

// Rebuilt (not just called once) so `rerender` re-mounts under the same provider
// and picks up a mid-test change to `pluginConfig`.
function chatTree() {
  return (
    <IntlTestProvider messages={composeEn}>
      <ChatInterfaceInner conversationId={null} />
    </IntlTestProvider>
  );
}

function renderChat() {
  return render(chatTree());
}

// Drives the real ChatInput -> useChatInput -> guarded onSend path, rather than
// calling the guard directly. Enter submits the same handleSend the send button's
// onClick does; the send button itself is an icon with no accessible name to query.
async function sendFromInput(text = "a course about chess") {
  const box = screen.getByPlaceholderText(composeEn.compose.inputPlaceholder);
  fireEvent.change(box, { target: { value: text } });
  await act(async () => {
    fireEvent.keyDown(box, { key: "Enter" });
  });
}

describe("ChatInterfaceInner — AI key guidance", () => {
  beforeEach(() => vi.clearAllMocks());

  it("tells an author with no AI key to add one and select it", async () => {
    pluginConfig = {};
    mockedFetchLLMConfigs.mockResolvedValue({ configs: [], total: 0 });

    renderChat();
    await sendFromInput();

    expect(await screen.findByText(/have not added an AI key to Sparkth yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add an AI key" })).toHaveAttribute(
      "href",
      "/dashboard/llm/configure",
    );
  });

  it("tells an author with a key to select it", async () => {
    pluginConfig = {};
    mockedFetchLLMConfigs.mockResolvedValue({ configs: [], total: 1 });

    renderChat();
    await sendFromInput();

    expect(
      await screen.findByText(/Select your AI key in Compose's configuration/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open plugin settings" })).toHaveAttribute(
      "href",
      "/dashboard/settings",
    );
  });

  it("asks nothing of the API when a key is already selected", async () => {
    pluginConfig = { llm_config_id: 1 };

    renderChat();
    await sendFromInput();

    expect(mockedFetchLLMConfigs).not.toHaveBeenCalled();
  });

  it("clears the alert once a later send finds the key ready", async () => {
    pluginConfig = {};
    mockedFetchLLMConfigs.mockResolvedValue({ configs: [], total: 0 });

    const { rerender } = renderChat();
    await sendFromInput();
    expect(await screen.findByText(/have not added an AI key to Sparkth yet/i)).toBeInTheDocument();

    pluginConfig = { llm_config_id: 1 };
    rerender(chatTree());
    await sendFromInput();

    expect(screen.queryByText(/have not added an AI key to Sparkth yet/i)).not.toBeInTheDocument();
  });

  it("shares one in-flight check across two overlapping sends", async () => {
    pluginConfig = {};
    let resolveFetch!: (value: Awaited<ReturnType<typeof fetchLLMConfigs>>) => void;
    mockedFetchLLMConfigs.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    renderChat();
    const box = screen.getByPlaceholderText(composeEn.compose.inputPlaceholder);
    fireEvent.change(box, { target: { value: "a course about chess" } });
    fireEvent.keyDown(box, { key: "Enter" });
    fireEvent.keyDown(box, { key: "Enter" });

    await act(async () => {
      resolveFetch({ configs: [], total: 0 });
    });

    expect(mockedFetchLLMConfigs).toHaveBeenCalledOnce();
  });

  it("keeps the typed message when a turn is still running in this conversation", async () => {
    pluginConfig = { llm_config_id: 1 };
    turnLive = true;

    renderChat();
    await sendFromInput("a second message");
    turnLive = false;

    expect(mockHandleSend).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder)).toHaveValue(
      "a second message",
    );
  });

  it("puts a checked option into the message box", async () => {
    pluginConfig = {};
    mockedFetchLLMConfigs.mockResolvedValue({ configs: [], total: 0 });

    renderChat();
    fireEvent.click(screen.getByText("Option"));
    fireEvent.click(screen.getByText("Option"));

    expect(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder)).toHaveValue(
      "Beginners",
    );
  });
});

describe("ChatInterfaceInner — a chat that fails to load", () => {
  beforeEach(() => {
    loadError = null;
  });

  it("shows a not-found page instead of the chat when the chat does not exist", () => {
    loadError = "notFound";

    renderChat();

    expect(
      screen.getByRole("heading", { name: composeEn.compose.chatNotFoundTitle }),
    ).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(composeEn.compose.inputPlaceholder)).toBeNull();
    // By its visible text: the header's icon link carries the same accessible name.
    expect(screen.getByText(composeEn.compose.historyNewChat)).toHaveAttribute(
      "href",
      "/dashboard/compose",
    );
  });

  it("shows an error instead of the chat when the chat could not be loaded", () => {
    loadError = "failed";

    renderChat();

    expect(screen.getByRole("alert")).toHaveTextContent(composeEn.compose.chatLoadFailedMessage);
    expect(screen.queryByPlaceholderText(composeEn.compose.inputPlaceholder)).toBeNull();
    // A chat that may still exist is not shown as missing.
    expect(screen.queryByRole("heading", { name: composeEn.compose.chatNotFoundTitle })).toBeNull();
  });
});
