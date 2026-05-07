"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { KeyRound } from "lucide-react";

import { Spinner } from "@/components/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { useAuth } from "@/lib/auth-context";
import { createLLMConfig, fetchProviderCatalog, type ProviderInfo } from "@/lib/llm-api";

// ─── Name validation ──────────────────────────────────────────────────────────

const NAME_PATTERN = /^[a-zA-Z0-9_-]+$/;

function validateName(name: string): string {
  if (!name.trim()) return "Name is required";
  if (!NAME_PATTERN.test(name)) return "Only letters, numbers, hyphens, and underscores allowed";
  if (name.length > 100) return "Name must be 100 characters or less";
  return "";
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function NewLLMConfigPage() {
  const router = useRouter();
  const { token, loading: authLoading } = useAuth();

  // Catalog state
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");

  // Form field state
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [apiKey, setApiKey] = useState("");

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  // Load provider catalog
  const loadCatalog = useCallback(async () => {
    if (!token) {
      setCatalogLoading(false);
      return;
    }

    setCatalogLoading(true);
    setCatalogError("");
    try {
      const catalog = await fetchProviderCatalog(token);
      setProviders(catalog.providers);

      // Pre-select default provider and model
      if (catalog.default_provider) {
        setSelectedProvider(catalog.default_provider);
        const defaultProviderInfo = catalog.providers.find(
          (p) => p.id === catalog.default_provider,
        );
        const firstModel = catalog.default_model || (defaultProviderInfo?.models?.[0] ?? "");
        setSelectedModel(firstModel);
      } else if (catalog.providers.length > 0) {
        const firstProvider = catalog.providers[0];
        setSelectedProvider(firstProvider.id);
        setSelectedModel(firstProvider.models[0] ?? "");
      }
    } catch (e) {
      setCatalogError(e instanceof Error ? e.message : "Failed to load provider catalog");
    } finally {
      setCatalogLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  // Wait for auth to resolve
  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!token) return null;

  // Provider change resets model to first model of new provider
  function handleProviderChange(providerId: string) {
    setSelectedProvider(providerId);
    const providerInfo = providers.find((p) => p.id === providerId);
    setSelectedModel(providerInfo?.models?.[0] ?? "");
  }

  // Derived model options for selected provider
  const currentProviderInfo = providers.find((p) => p.id === selectedProvider);
  const modelOptions = (currentProviderInfo?.models ?? []).map((m) => ({
    value: m,
    label: m,
  }));

  const providerOptions = providers.map((p) => ({ value: p.id, label: p.label }));

  // Form validity
  const nameValid = !validateName(name);
  const formValid =
    !catalogError &&
    nameValid &&
    name.trim().length > 0 &&
    selectedProvider !== "" &&
    selectedModel !== "" &&
    apiKey.trim() !== "";

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const nameErr = validateName(name);
    if (nameErr) {
      setNameError(nameErr);
      return;
    }

    if (!selectedProvider || !selectedModel || !apiKey.trim()) return;

    setSubmitting(true);
    setSubmitError("");
    try {
      await createLLMConfig(token!, {
        name: name.trim(),
        provider: selectedProvider,
        model: selectedModel,
        api_key: apiKey.trim(),
      });
      router.push("/dashboard/llm/configure/");
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Failed to create LLM config");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6 sm:mb-8">
          <div className="flex items-center gap-3 mb-2">
            <KeyRound className="h-6 w-6 text-primary-600" aria-hidden="true" />
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">New LLM Config</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Add an API key and model configuration for an LLM provider.
          </p>
        </div>

        {/* Catalog loading state */}
        {catalogLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <Spinner className="mx-auto mb-4" />
              <p className="text-muted-foreground">Loading providers...</p>
            </div>
          </div>
        ) : (
          <div className="bg-card rounded-lg shadow-sm border border-border max-w-xl">
            <div className="px-6 py-6">
              {/* Catalog error (non-blocking) */}
              {catalogError && (
                <Alert severity="error" className="mb-6">
                  {catalogError}
                </Alert>
              )}

              {/* Submit error */}
              {submitError && (
                <Alert severity="error" className="mb-6">
                  {submitError}
                </Alert>
              )}

              <form aria-label="Create LLM config" onSubmit={handleSubmit} noValidate>
                <div className="space-y-5">
                  {/* Name field */}
                  <Input
                    label="Name"
                    name="name"
                    required
                    placeholder="e.g. my-openai-key"
                    value={name}
                    error={nameError}
                    autoFocus
                    onChange={(e) => {
                      setName(e.target.value);
                      if (nameError) setNameError(validateName(e.target.value));
                    }}
                    onBlur={(e) => setNameError(validateName(e.target.value))}
                    disabled={submitting || !!catalogError}
                  />

                  {/* Provider field */}
                  <Select
                    label="Provider"
                    name="provider"
                    required
                    placeholder="Select a provider"
                    value={selectedProvider}
                    options={providerOptions}
                    onChange={(e) => handleProviderChange(e.target.value)}
                    disabled={submitting || !!catalogError || providers.length === 0}
                  />

                  {/* Model field — wrapped for a11y live announcement */}
                  <div aria-live="polite">
                    <Select
                      label="Model"
                      name="model"
                      required
                      placeholder="Select a model"
                      value={selectedModel}
                      options={modelOptions}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      disabled={
                        submitting ||
                        !!catalogError ||
                        !selectedProvider ||
                        modelOptions.length === 0
                      }
                    />
                  </div>

                  {/* API Key field */}
                  <Input
                    label="API Key"
                    name="api_key"
                    type="password"
                    required
                    autoComplete="off"
                    placeholder="sk-..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    disabled={submitting || !!catalogError}
                  />
                </div>

                {/* Actions */}
                <div className="mt-8 flex items-center justify-end gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => router.push("/dashboard/llm/configure/")}
                    disabled={submitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    loading={submitting}
                    spinnerLabel="Creating"
                    disabled={!formValid || submitting}
                  >
                    Create Config
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
