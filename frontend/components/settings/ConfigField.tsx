"use client";

import { isUrlKey, formatConfigKey, isValidUrl } from "./utils";

interface PluginConfigFieldProps {
  name: string;
  value: string | null;
  onChange: (key: string, value: string) => void;
  error?: string;
  setError: (key: string, errorMsg: string) => void;
}

export function PluginConfigField({
  name,
  value,
  onChange,
  error,
  setError,
}: PluginConfigFieldProps) {
  const isUrl = isUrlKey(name);

  const handleChange = (val: string) => {
    onChange(name, val);

    if (!val) {
      setError(name, "This field is required");
      return;
    }

    if (isUrl && !isValidUrl(val)) {
      setError(name, "Input should be a valid URL");
      return;
    }

    setError(name, "");
  };

  return (
    <div className="space-y-1">
      <label className="text-sm font-medium text-foreground">
        {formatConfigKey(name)}
      </label>

      <input
        type={isUrl ? "url" : "text"}
        inputMode={isUrl ? "url" : "text"}
        placeholder={isUrl ? "https://example.com" : undefined}
        value={value ?? ""}
        onChange={(e) => handleChange(e.target.value)}
        className={`w-full px-3 py-3 rounded-lg text-sm bg-input text-foreground placeholder-muted focus:outline-none focus:ring-2 transition-colors ${
          error
            ? "border border-error-500 focus:ring-error-500"
            : "border border-border focus:ring-ring"
        }`}
      />
      {error && (
        <p className="text-xs text-error-600 dark:text-error-400">{error}</p>
      )}
    </div>
  );
}
