export const isUrlKey = (key: string) => key.toLowerCase().includes("url");

export const isValidUrl = (value: string) => {
  if (!value) return true;
  try {
    new URL(value);
    return true;
  } catch {
    return false;
  }
};

export const isConfigured = (config: Record<string, unknown>) =>
  Object.values(config).some((v) => v !== null && v !== undefined && v !== "");

export const formatConfigKey = (key: string) =>
  key.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
