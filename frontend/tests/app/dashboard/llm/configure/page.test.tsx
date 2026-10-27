import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "t" }) }));
vi.mock("@/lib/llm", () => ({
  fetchLLMConfigs: vi.fn(),
  fetchProviderCatalog: vi.fn(),
  setLLMConfigActive: vi.fn(),
  createLLMConfig: vi.fn(),
  updateLLMConfig: vi.fn(),
  deleteLLMConfig: vi.fn(),
  rotateLLMConfigKey: vi.fn(),
}));

import { fetchLLMConfigs, fetchProviderCatalog, setLLMConfigActive } from "@/lib/llm";
import LLMConfigurePage from "@/app/dashboard/llm/configure/page";
import { renderWithIntl } from "@/tests/intl-test-utils";

const config = {
  id: 1,
  name: "my-key",
  provider: "openai",
  model: "gpt-4o",
  masked_key: "sk-****abcd",
  is_active: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchLLMConfigs).mockResolvedValue({ configs: [config] } as never);
  vi.mocked(fetchProviderCatalog).mockResolvedValue({ providers: [] } as never);
});

describe("AI Keys page", () => {
  it("lists a config in a shared settings row", async () => {
    renderWithIntl(<LLMConfigurePage />);
    expect(await screen.findByRole("switch", { name: "Turn my-key on or off" })).toBeDefined();
    expect(screen.getByText("sk-****abcd")).toBeDefined();
    expect(screen.getByText("Active")).toBeDefined();
    expect(screen.getByRole("button", { name: "Edit config my-key" })).toBeDefined();
  });

  it("keeps the list and shows a failed toggle in the row", async () => {
    vi.mocked(setLLMConfigActive).mockRejectedValue(new Error("nope"));
    renderWithIntl(<LLMConfigurePage />);

    fireEvent.click(await screen.findByRole("switch", { name: "Turn my-key on or off" }));

    expect(await screen.findByText("nope")).toBeDefined();
    expect(screen.getByRole("listitem").textContent).toContain("my-key");
  });

  it("checks a config name as it is typed", async () => {
    renderWithIntl(<LLMConfigurePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit config my-key" }));
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "bad name!" },
    });

    expect(
      await screen.findByText("Only letters, numbers, hyphens, and underscores allowed"),
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "Save Changes" })).toBeDisabled();
  });
});
