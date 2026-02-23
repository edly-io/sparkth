"use client";

import { isUrlKey, formatConfigKey, isValidUrl } from "./utils";
import { Input } from "@/components/ui/Input";

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
    <Input
      label={formatConfigKey(name)}
      type={isUrl ? "url" : "text"}
      inputMode={isUrl ? "url" : "text"}
      placeholder={isUrl ? "https://example.com" : undefined}
      value={value ?? ""}
      onChange={(e) => handleChange(e.target.value)}
      error={error}
    />
  );
}
