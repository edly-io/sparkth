/**
 * The settings form, derived from a plugin's declared JSON schema.
 *
 * A backend plugin registers a Pydantic config class (`CONFIG_SCHEMAS`); the
 * user-plugins API ships its `model_json_schema()` as `config_schema`. These readers
 * turn that schema into the field descriptors the generic settings modal renders, so
 * a plugin becomes configurable by declaring its config — no frontend code required.
 *
 * A field's control comes from its `widget` hint (set with `json_schema_extra` on the
 * Pydantic field, see `sparkth/core/plugins/widgets.py`) and, failing that, from its
 * type and format.
 */

/** A JSON-schema fragment. Values are `unknown`: the schema is data from the API. */
type SchemaObject = Record<string, unknown>;

export type ConfigFieldType = "string" | "integer" | "number" | "boolean" | "array";

export interface ConfigFieldDescriptor {
  name: string;
  label: string;
  description?: string;
  /** Registry key of the control that renders this field. */
  widget: string;
  type: ConfigFieldType;
  /** The schema lists the field in `required` — it has no default to fall back on. */
  required: boolean;
  /** The field accepts null, so leaving it unset is meaningful. */
  nullable: boolean;
  default?: unknown;
  minimum?: number;
  maximum?: number;
}

const asObject = (value: unknown): SchemaObject | undefined =>
  typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as SchemaObject)
    : undefined;

const asString = (value: unknown): string | undefined =>
  typeof value === "string" ? value : undefined;

const asNumber = (value: unknown): number | undefined =>
  typeof value === "number" && Number.isFinite(value) ? value : undefined;

/** `api_key` → `Api Key`, for a field whose schema carries no title. */
const humanize = (key: string) =>
  key.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

/**
 * The variants of an optional field, which Pydantic emits as `anyOf: [T, null]`.
 * A field with a single type yields just itself.
 */
function variantsOf(property: SchemaObject): SchemaObject[] {
  const anyOf = property.anyOf;
  if (!Array.isArray(anyOf)) return [property];
  return anyOf.map(asObject).filter((variant): variant is SchemaObject => variant !== undefined);
}

function typeOf(property: SchemaObject): ConfigFieldType {
  const named = variantsOf(property)
    .map((variant) => asString(variant.type))
    .find((type) => type !== undefined && type !== "null");

  switch (named) {
    case "integer":
    case "number":
    case "boolean":
    case "array":
      return named;
    default:
      return "string";
  }
}

/** The non-null variant, which carries the format and bounds of an optional field. */
function valueSchemaOf(property: SchemaObject): SchemaObject {
  return variantsOf(property).find((variant) => variant.type !== "null") ?? property;
}

function widgetOf(property: SchemaObject, type: ConfigFieldType): string {
  const declared = asString(property.widget);
  if (declared) return declared;

  if (type === "boolean") return "checkbox";
  if (type === "number" || type === "integer") return "number";
  if (type === "array") return "tags";
  return asString(valueSchemaOf(property).format) === "uri" ? "url" : "text";
}

/** The fields to render for a plugin, in the order its config class declares them. */
export function configFieldsOf(schema: SchemaObject | undefined): ConfigFieldDescriptor[] {
  const properties = asObject(schema?.properties);
  if (!properties) return [];

  const required = Array.isArray(schema?.required) ? schema.required : [];

  return Object.entries(properties).flatMap(([name, rawProperty]) => {
    const property = asObject(rawProperty);
    if (!property) return [];

    const type = typeOf(property);
    const valueSchema = valueSchemaOf(property);

    return [
      {
        name,
        label: asString(property.title) ?? humanize(name),
        description: asString(property.description),
        widget: widgetOf(property, type),
        type,
        required: required.includes(name),
        nullable: variantsOf(property).some((variant) => variant.type === "null"),
        default: property.default,
        minimum: asNumber(valueSchema.minimum),
        maximum: asNumber(valueSchema.maximum),
      },
    ];
  });
}

/** The form's starting values: the stored config, falling back to the schema defaults. */
export function initialValuesOf(
  fields: ConfigFieldDescriptor[],
  config: Record<string, unknown> | undefined,
): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => {
      const stored = config?.[field.name];
      if (stored !== undefined && stored !== null) return [field.name, stored];
      if (field.default !== undefined && field.default !== null) return [field.name, field.default];
      return [field.name, field.type === "array" ? [] : ""];
    }),
  );
}

// An empty array is a value ("no sources selected"), not an empty field.
const isEmpty = (value: unknown) => value === "" || value === undefined || value === null;

/** The error to show under a field, or `undefined` when the value is acceptable. */
export function validateField(field: ConfigFieldDescriptor, value: unknown): string | undefined {
  if (isEmpty(value)) {
    if (field.required) return "This field is required";
    // A nullable field is unset rather than empty, and a field whose default is the
    // empty string declares that empty is a value it accepts.
    if (field.nullable || field.type === "array" || field.type === "boolean") return undefined;
    if (field.default === "") return undefined;
    return "This field is required";
  }

  if (field.type === "number" || field.type === "integer") {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return "Enter a number";
    if (field.minimum !== undefined && parsed < field.minimum)
      return `Enter a value of at least ${field.minimum}`;
    if (field.maximum !== undefined && parsed > field.maximum)
      return `Enter a value of at most ${field.maximum}`;
    return undefined;
  }

  if (field.widget === "url") {
    try {
      new URL(String(value));
    } catch {
      return "Input should be a valid URL";
    }
  }

  return undefined;
}

/** The first error across every field, keyed by field name. */
export function validateFields(
  fields: ConfigFieldDescriptor[],
  values: Record<string, unknown>,
): Record<string, string> {
  return Object.fromEntries(
    fields.flatMap((field) => {
      const error = validateField(field, values[field.name]);
      return error ? [[field.name, error]] : [];
    }),
  );
}

/**
 * The body to PUT: declared fields only, typed as the backend's Pydantic model
 * expects them (it validates in strict mode, so a number must not arrive as a string).
 */
export function payloadOf(
  fields: ConfigFieldDescriptor[],
  values: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => {
      const value = values[field.name];

      if (field.type === "array") return [field.name, Array.isArray(value) ? value : []];
      if (field.type === "boolean") return [field.name, Boolean(value)];
      // A field the model does not accept as null stays a string; only a nullable
      // one is genuinely unset.
      if (isEmpty(value))
        return [field.name, field.nullable || field.type !== "string" ? null : ""];
      if (field.type === "number") return [field.name, Number(value)];
      if (field.type === "integer") return [field.name, Math.trunc(Number(value))];
      return [field.name, value];
    }),
  );
}
