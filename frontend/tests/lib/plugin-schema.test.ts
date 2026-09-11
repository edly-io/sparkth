import { describe, it, expect } from "vitest";

import { configFieldsOf, initialValuesOf, validateField, payloadOf } from "@/lib/plugins/schema";

// The shape Pydantic's model_json_schema() emits, as the user-plugins API ships it.
const SLACK_SCHEMA = {
  title: "SlackConfig",
  type: "object",
  properties: {
    bot_name: { title: "Bot Name", type: "string", default: "TA Bot" },
    fallback_message: {
      title: "Fallback Message",
      type: "string",
      default: "No answer found.",
      description: "Message sent when no RAG match is found",
      widget: "textarea",
    },
    allowed_sources: {
      title: "Allowed Sources",
      type: "array",
      items: { type: "string" },
      widget: "doc-sources",
    },
    llm_config_id: {
      anyOf: [{ type: "integer" }, { type: "null" }],
      title: "Llm Config Id",
      default: null,
      widget: "llm-config",
    },
    llm_temperature: {
      title: "Llm Temperature",
      type: "number",
      default: 0.3,
      minimum: 0,
      maximum: 2,
    },
  },
};

const OPENEDX_SCHEMA = {
  title: "OpenEdxConfig",
  type: "object",
  properties: {
    lms_url: { title: "Lms Url", type: "string", format: "uri", minLength: 1 },
    lms_password: { title: "Lms Password", type: "string", minLength: 1, widget: "password" },
  },
  required: ["lms_url", "lms_password"],
};

describe("configFieldsOf", () => {
  it("returns no fields for a plugin that declared no schema", () => {
    expect(configFieldsOf({})).toEqual([]);
  });

  it("keeps the order the schema declares", () => {
    expect(configFieldsOf(SLACK_SCHEMA).map((f) => f.name)).toEqual([
      "bot_name",
      "fallback_message",
      "allowed_sources",
      "llm_config_id",
      "llm_temperature",
    ]);
  });

  it("reads the declared widget, and infers one from the type otherwise", () => {
    const byName = Object.fromEntries(configFieldsOf(SLACK_SCHEMA).map((f) => [f.name, f]));
    expect(byName.fallback_message.widget).toBe("textarea");
    expect(byName.allowed_sources.widget).toBe("doc-sources");
    expect(byName.llm_config_id.widget).toBe("llm-config");
    expect(byName.bot_name.widget).toBe("text");
    expect(byName.llm_temperature.widget).toBe("number");
  });

  it("infers url and password widgets from format and hint", () => {
    const byName = Object.fromEntries(configFieldsOf(OPENEDX_SCHEMA).map((f) => [f.name, f]));
    expect(byName.lms_url.widget).toBe("url");
    expect(byName.lms_password.widget).toBe("password");
  });

  it("carries title, description, default and numeric bounds", () => {
    const [botName, fallback, , , temperature] = configFieldsOf(SLACK_SCHEMA);
    expect(botName.label).toBe("Bot Name");
    expect(botName.default).toBe("TA Bot");
    expect(fallback.description).toBe("Message sent when no RAG match is found");
    expect(temperature.minimum).toBe(0);
    expect(temperature.maximum).toBe(2);
  });

  it("labels a field the schema gave no title from its key", () => {
    const [field] = configFieldsOf({ properties: { api_key: { type: "string" } } });
    expect(field.label).toBe("Api Key");
  });

  it("resolves the type through an optional field's anyOf", () => {
    const [field] = configFieldsOf({
      properties: { llm_config_id: SLACK_SCHEMA.properties.llm_config_id },
    });
    expect(field.type).toBe("integer");
    expect(field.nullable).toBe(true);
  });

  it("marks fields listed in required, and only those", () => {
    const byName = Object.fromEntries(configFieldsOf(OPENEDX_SCHEMA).map((f) => [f.name, f]));
    expect(byName.lms_url.required).toBe(true);

    const optional = Object.fromEntries(configFieldsOf(SLACK_SCHEMA).map((f) => [f.name, f]));
    expect(optional.llm_config_id.required).toBe(false);
  });
});

describe("initialValuesOf", () => {
  it("prefers the stored value over the schema default", () => {
    const values = initialValuesOf(configFieldsOf(SLACK_SCHEMA), { bot_name: "Course Bot" });
    expect(values.bot_name).toBe("Course Bot");
  });

  it("falls back to the schema default when the config has no value", () => {
    const values = initialValuesOf(configFieldsOf(SLACK_SCHEMA), {});
    expect(values.bot_name).toBe("TA Bot");
    expect(values.llm_temperature).toBe(0.3);
  });

  it("treats a null stored value as unset", () => {
    const values = initialValuesOf(configFieldsOf(SLACK_SCHEMA), { bot_name: null });
    expect(values.bot_name).toBe("TA Bot");
  });

  it("defaults an array field to an empty array", () => {
    const values = initialValuesOf(configFieldsOf(SLACK_SCHEMA), {});
    expect(values.allowed_sources).toEqual([]);
  });

  it("ignores config keys the schema does not declare", () => {
    // The LLM adapter adds read-only llm_config_name / llm_provider / llm_model.
    const values = initialValuesOf(configFieldsOf(SLACK_SCHEMA), { llm_provider: "anthropic" });
    expect(values).not.toHaveProperty("llm_provider");
  });
});

describe("validateField", () => {
  const [lmsUrl, lmsPassword] = configFieldsOf(OPENEDX_SCHEMA);
  const fields = configFieldsOf(SLACK_SCHEMA);
  const temperature = fields.find((f) => f.name === "llm_temperature")!;
  const llmConfigId = fields.find((f) => f.name === "llm_config_id")!;

  it("rejects an empty required field", () => {
    expect(validateField(lmsPassword, "")).toBe("This field is required");
  });

  it("rejects an empty non-nullable field even when it has a default", () => {
    const botName = fields.find((f) => f.name === "bot_name")!;
    expect(validateField(botName, "")).toBeTruthy();
  });

  it("accepts an empty nullable field", () => {
    expect(validateField(llmConfigId, "")).toBeUndefined();
  });

  it("accepts an empty value for a field whose default is the empty string", () => {
    const [note] = configFieldsOf({ properties: { note: { type: "string", default: "" } } });
    expect(validateField(note, "")).toBeUndefined();
  });

  it("rejects a malformed url", () => {
    expect(validateField(lmsUrl, "not-a-url")).toBe("Input should be a valid URL");
    expect(validateField(lmsUrl, "https://lms.example.com")).toBeUndefined();
  });

  it("rejects a number outside the declared bounds", () => {
    expect(validateField(temperature, 2.5)).toBeTruthy();
    expect(validateField(temperature, -1)).toBeTruthy();
    expect(validateField(temperature, 1.5)).toBeUndefined();
  });

  it("rejects a non-numeric value in a number field", () => {
    expect(validateField(temperature, "abc")).toBeTruthy();
  });
});

describe("payloadOf", () => {
  it("sends numbers as numbers, not strings", () => {
    const payload = payloadOf(configFieldsOf(SLACK_SCHEMA), {
      bot_name: "TA Bot",
      llm_temperature: "0.7",
      allowed_sources: ["notes.pdf"],
    });
    expect(payload.llm_temperature).toBe(0.7);
    expect(payload.allowed_sources).toEqual(["notes.pdf"]);
  });

  it("sends an unset nullable field as null", () => {
    const payload = payloadOf(configFieldsOf(SLACK_SCHEMA), { llm_config_id: "" });
    expect(payload.llm_config_id).toBeNull();
  });

  it("sends an empty non-nullable string as an empty string, not null", () => {
    const fields = configFieldsOf({ properties: { note: { type: "string", default: "" } } });
    expect(payloadOf(fields, { note: "" })).toEqual({ note: "" });
  });

  it("sends only the fields the schema declares", () => {
    const payload = payloadOf(configFieldsOf(SLACK_SCHEMA), {
      bot_name: "TA Bot",
      llm_provider: "anthropic",
    });
    expect(payload).not.toHaveProperty("llm_provider");
  });
});
