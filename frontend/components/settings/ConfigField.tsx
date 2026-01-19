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
      <label className="text-sm font-medium text-edly-gray-700">
        {formatConfigKey(name)}
      </label>

      <input
        type={isUrl ? "url" : "text"}
        inputMode={isUrl ? "url" : "text"}
        placeholder={isUrl ? "https://example.com" : undefined}
        value={value ?? ""}
        onChange={(e) => handleChange(e.target.value)}
        className={`w-full px-3 py-3 rounded-lg text-sm focus:outline-none focus:ring-2 ${
          error
            ? "border border-edly-red-300 focus:ring-red-500"
            : "border border-gray-300 focus:ring-primary-500"
        } text-edly-gray-900`}
      />
      {error && <p className="text-xs text-edly-red-600">{error}</p>}
    </div>
  );
}
