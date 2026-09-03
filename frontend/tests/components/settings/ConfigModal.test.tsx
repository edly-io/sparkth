import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { PluginConfigModal } from "@/components/settings/ConfigModal";
import type { UserPluginState } from "@/lib/plugins";

const OPENEDX_SCHEMA = {
  title: "OpenEdxConfig",
  type: "object",
  properties: {
    lms_url: { title: "Lms Url", type: "string", format: "uri" },
    lms_username: { title: "Lms Username", type: "string" },
    lms_password: { title: "Lms Password", type: "string", widget: "password" },
    note: { title: "Note", type: "string", widget: "textarea", default: "" },
  },
  required: ["lms_url", "lms_username", "lms_password"],
};

function renderModal(plugin: Partial<UserPluginState>, onSave = vi.fn(async () => {})) {
  render(
    <PluginConfigModal
      plugin={{
        plugin_name: "open-edx",
        enabled: true,
        config: {},
        config_schema: OPENEDX_SCHEMA,
        is_core: true,
        display: null,
        sidebar: null,
        has_frontend: false,
        ...plugin,
      }}
      open
      onOpenChange={vi.fn()}
      onSave={onSave}
      onRefresh={vi.fn()}
    />,
  );
  return onSave;
}

describe("PluginConfigModal", () => {
  it("renders one field per schema property, labelled by its title", () => {
    renderModal({});

    expect(screen.getByLabelText(/Lms Url/)).toBeDefined();
    expect(screen.getByLabelText(/Lms Username/)).toBeDefined();
    expect(screen.getByLabelText(/Lms Password/)).toBeDefined();
  });

  it("masks a field the schema marks as a password", () => {
    renderModal({});
    expect(screen.getByLabelText(/Lms Password/).getAttribute("type")).toBe("password");
  });

  it("renders a textarea field as a textarea", () => {
    renderModal({});
    expect(screen.getByLabelText(/Note/).tagName).toBe("TEXTAREA");
  });

  it("prefills the stored config", () => {
    renderModal({ config: { lms_url: "https://lms.example.com" } });
    expect((screen.getByLabelText(/Lms Url/) as HTMLInputElement).value).toBe(
      "https://lms.example.com",
    );
  });

  it("says so when the plugin declares no configuration", () => {
    renderModal({ config_schema: {} });
    expect(screen.getByText(/No configuration options available/)).toBeDefined();
  });

  it("renders fields even when the stored config is empty", () => {
    // Enabling a plugin stores {}; the form must still come from the schema.
    renderModal({ config: {} });
    expect(screen.getByLabelText(/Lms Url/)).toBeDefined();
  });

  it("does not render config keys the schema does not declare", () => {
    // The LLM adapter adds read-only llm_provider / llm_model to the config.
    renderModal({ config: { llm_provider: "anthropic" } });
    expect(screen.queryByLabelText(/Llm Provider/)).toBeNull();
  });

  it("reports an invalid url and refuses to save", async () => {
    const onSave = renderModal({});

    fireEvent.change(screen.getByLabelText(/Lms Url/), { target: { value: "not-a-url" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText("Input should be a valid URL")).toBeDefined();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("refuses to save while a required field is empty", async () => {
    const onSave = renderModal({ config: { lms_url: "https://lms.example.com" } });

    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findAllByText("This field is required")).toHaveLength(2);
    expect(onSave).not.toHaveBeenCalled();
  });

  it("saves the declared fields once every value is valid", async () => {
    const onSave = renderModal({});

    fireEvent.change(screen.getByLabelText(/Lms Url/), {
      target: { value: "https://lms.example.com" },
    });
    fireEvent.change(screen.getByLabelText(/Lms Username/), { target: { value: "staff" } });
    fireEvent.change(screen.getByLabelText(/Lms Password/), { target: { value: "s3cret" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        lms_url: "https://lms.example.com",
        lms_username: "staff",
        lms_password: "s3cret",
        note: "",
      }),
    );
  });

  it("sends a number field as a number", async () => {
    const onSave = renderModal({
      config_schema: {
        properties: {
          temperature: {
            title: "Temperature",
            type: "number",
            default: 0.3,
            minimum: 0,
            maximum: 2,
          },
        },
      },
    });

    fireEvent.change(screen.getByLabelText(/Temperature/), { target: { value: "0.7" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith({ temperature: 0.7 }));
  });

  it("refuses a number outside the declared bounds", async () => {
    const onSave = renderModal({
      config_schema: {
        properties: {
          temperature: {
            title: "Temperature",
            type: "number",
            default: 0.3,
            minimum: 0,
            maximum: 2,
          },
        },
      },
    });

    fireEvent.change(screen.getByLabelText(/Temperature/), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText(/at most 2/)).toBeDefined();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("surfaces a failed save", async () => {
    const onSave = vi.fn(async () => {
      throw new Error("boom");
    });
    renderModal(
      { config: { lms_url: "https://l.example.com", lms_username: "s", lms_password: "p" } },
      onSave,
    );

    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText(/Failed to save configuration/)).toBeDefined();
  });
});
