import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";

import { renderWithIntl } from "@/tests/intl-test-utils";
import { PluginConfigModal } from "@/core/components/settings/ConfigModal";
import type { UserPluginState } from "@/core/plugins/types";
import type { ConfigWidgetProps } from "@/lib/settings/slots";
import type { ComponentType } from "react";

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

function renderModal(
  plugin: Partial<UserPluginState>,
  onSave = vi.fn(async () => {}),
  controls?: Record<string, ComponentType<ConfigWidgetProps>>,
) {
  renderWithIntl(
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
        secrets_set: [],
        masked_secrets: {},
        ...plugin,
      }}
      open
      onOpenChange={vi.fn()}
      onSave={onSave}
      onRefresh={vi.fn()}
      controls={controls}
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

  it("checks a field as it is typed", async () => {
    renderModal({});
    fireEvent.change(screen.getByLabelText(/Lms Url/), { target: { value: "not a url" } });
    expect(await screen.findByText("Input should be a valid URL")).toBeDefined();
  });

  it("shows every field's error when Save is clicked on an incomplete form", async () => {
    const onSave = renderModal({ config: { lms_url: "https://lms.example.com" } });

    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findAllByText("This field is required")).toHaveLength(2);
    expect(onSave).not.toHaveBeenCalled();
  });

  it("shows the server's reason when a save fails", async () => {
    const onSave = vi.fn(async () => {
      throw new Error("Canvas rejected the key");
    });
    renderModal(
      { config: { lms_url: "https://l.example.com", lms_username: "s", lms_password: "p" } },
      onSave,
    );

    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText("Canvas rejected the key")).toBeDefined();
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
      throw new Error("");
    });
    renderModal(
      { config: { lms_url: "https://l.example.com", lms_username: "s", lms_password: "p" } },
      onSave,
    );

    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText(/Failed to save configuration/)).toBeDefined();
  });

  it("shows a stored secret as dots, never as a value", () => {
    renderModal({
      config: { lms_url: "https://l.example.com", lms_username: "s" },
      secrets_set: ["lms_password"],
      masked_secrets: {},
    });

    expect(screen.getByText("••••••••")).toBeDefined();
    // The selector skips the Replace button, whose aria-label also mentions the field.
    expect(screen.queryByLabelText(/Lms Password/, { selector: "input" })).toBeNull();
    expect(screen.getByRole("button", { name: "Replace Lms Password" })).toBeDefined();
  });

  it("keeps a stored secret it was not asked to replace", async () => {
    const onSave = renderModal({
      config: { lms_url: "https://l.example.com", lms_username: "s" },
      secrets_set: ["lms_password"],
      masked_secrets: {},
    });

    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        lms_url: "https://l.example.com",
        lms_username: "s",
        note: "",
      }),
    );
  });

  it("sends a replaced secret", async () => {
    const onSave = renderModal({
      config: { lms_url: "https://l.example.com", lms_username: "s" },
      secrets_set: ["lms_password"],
      masked_secrets: {},
    });

    fireEvent.click(screen.getByRole("button", { name: "Replace Lms Password" }));
    fireEvent.change(screen.getByLabelText(/Lms Password/, { selector: "input" }), {
      target: { value: "n3w" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ lms_password: "n3w" })),
    );
  });

  it("refuses to save a replaced secret left empty", async () => {
    const onSave = renderModal({
      config: { lms_url: "https://l.example.com", lms_username: "s" },
      secrets_set: ["lms_password"],
      masked_secrets: {},
    });

    fireEvent.click(screen.getByRole("button", { name: "Replace Lms Password" }));
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText("This field is required")).toBeDefined();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("keeps the stored secret again after a replace is undone", async () => {
    const onSave = renderModal({
      config: { lms_url: "https://l.example.com", lms_username: "s" },
      secrets_set: ["lms_password"],
      masked_secrets: {},
    });

    fireEvent.click(screen.getByRole("button", { name: "Replace Lms Password" }));
    fireEvent.change(screen.getByLabelText(/Lms Password/, { selector: "input" }), {
      target: { value: "typo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Keep stored Lms Password" }));
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        lms_url: "https://l.example.com",
        lms_username: "s",
        note: "",
      }),
    );
    expect(screen.getByText("••••••••")).toBeDefined();
  });
});

const PICKER_SCHEMA = {
  type: "object",
  properties: { picks: { title: "Picks", type: "string", widget: "example-picker" } },
};

function ExamplePicker({ field }: ConfigWidgetProps) {
  return <p>Example picker for {field.label}</p>;
}

describe("PluginConfigModal field controls", () => {
  it("renders the control passed for a field that names it", () => {
    renderModal(
      { config_schema: PICKER_SCHEMA },
      vi.fn(async () => {}),
      {
        "example-picker": ExamplePicker,
      },
    );

    expect(screen.getByText("Example picker for Picks")).toBeDefined();
  });

  it("renders a text input for a control nobody passed", () => {
    renderModal({ config_schema: PICKER_SCHEMA });

    expect(screen.getByLabelText("Picks").getAttribute("type")).toBe("text");
  });
});
