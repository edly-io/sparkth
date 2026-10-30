const NAME_PATTERN = /^[a-zA-Z0-9_-]+$/;

/** The error for an invalid AI key name, or an empty string when the name is valid. */
export function validateLLMConfigName(name: string): string {
  if (!name.trim()) return "Name is required";
  if (!NAME_PATTERN.test(name)) return "Only letters, numbers, hyphens, and underscores allowed";
  if (name.length > 100) return "Name must be 100 characters or less";
  return "";
}
