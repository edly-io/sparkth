import { act, fireEvent, screen } from "@testing-library/react";
import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, it, expect, vi, beforeEach } from "vitest";

import ChatInterfaceInner from "@/plugins/chat/components/ChatInterfaceInner";
import chatEn from "@/plugins/chat/messages/en.json";
import en from "@/messages/en.json";
import { fetchLLMConfigs } from "@/lib/llm/client";
import type { LLMConfigListResponse } from "@/lib/llm/types";

// usePlugin is mocked to read this directly, so a test sets it before rendering.
let pluginConfig: Record<string, unknown> = {};

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/plugins/context", () => ({
  usePlugin: () => ({ config: pluginConfig }),
}));

vi.mock("@/lib/plugins/usePlugins", () => ({
  useIsPluginEnabled: () => ({ isEnabled: false, loading: false }),
}));

vi.mock("@/components/drive/DriveFilePicker", () => ({
  default: () => null,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/plugins/chat/hooks/useConversation", () => ({
  useConversation: () => ({
    loading: false,
    messages: [],
    error: null,
    setError: vi.fn(),
    inputAttachments: [],
    setInputAttachments: vi.fn(),
    setMessages: vi.fn(),
    clearError: vi.fn(),
    skipNextLoadRef: { current: false },
  }),
}));

vi.mock("@/plugins/chat/hooks/useChatStream", () => ({
  useChatStream: () => ({
    handleSend: vi.fn(),
    handleOptionClick: vi.fn(),
    stopGeneration: vi.fn(),
    isStopping: false,
  }),
}));

vi.mock("@/lib/llm/client", () => ({
  fetchLLMConfigs: vi.fn(),
}));

const mockedFetchLLMConfigs = vi.mocked(fetchLLMConfigs);

// jsdom has no scrollIntoView implementation; ChatMessages calls it on mount.
Element.prototype.scrollIntoView = vi.fn();

// Rebuilt (not just called once) so `rerender` re-mounts under the same provider
// and picks up a mid-test change to `pluginConfig`.
function chatTree() {
  return (
    <NextIntlClientProvider locale="en" messages={{ ...en, ...chatEn }}>
      <ChatInterfaceInner conversationId={null} />
    </NextIntlClientProvider>
  );
}

function renderChat() {
  return render(chatTree());
}

// Drives the real ChatInput -> useChatInput -> checkAiKeyReady path, rather than
// calling the guard directly. Enter submits the same handleSend the send button's
// onClick does; the send button itself is an icon with no accessible name to query.
async function sendFromInput(text = "a course about chess") {
  const box = screen.getByPlaceholderText(chatEn.chat.inputPlaceholder);
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
    let resolveFetch!: (value: LLMConfigListResponse) => void;
    mockedFetchLLMConfigs.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    renderChat();
    const box = screen.getByPlaceholderText(chatEn.chat.inputPlaceholder);
    fireEvent.change(box, { target: { value: "a course about chess" } });
    fireEvent.keyDown(box, { key: "Enter" });
    fireEvent.keyDown(box, { key: "Enter" });

    await act(async () => {
      resolveFetch({ configs: [], total: 0 });
    });

    expect(mockedFetchLLMConfigs).toHaveBeenCalledOnce();
  });
});
