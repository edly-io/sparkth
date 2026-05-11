const NAME_PATTERN = /^[a-zA-Z0-9_-]+$/;

export function validateLLMConfigName(name: string): string {
  if (!name.trim()) return "Name is required";
  if (!NAME_PATTERN.test(name)) return "Only letters, numbers, hyphens, and underscores allowed";
  if (name.length > 100) return "Name must be 100 characters or less";
  return "";
}
