"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { KeyRound, Pencil, Plus, RotateCw, Save, Trash2 } from "lucide-react";

import { Spinner } from "@/core/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/core/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { SettingsList, SettingsPage } from "@/components/settings/SettingsPage";
import { SettingsRow } from "@/components/settings/SettingsRow";
import { useAuth } from "@/core/auth/hooks";
import { validateLLMConfigName } from "@/lib/llm-validation";
import {
  createLLMConfig,
  deleteLLMConfig,
  fetchLLMConfigs,
  fetchProviderCatalog,
  rotateLLMConfigKey,
  setLLMConfigActive,
  updateLLMConfig,
  type LLMConfig,
  type ProviderInfo,
} from "@/lib/llm";

// ─── Edit Modal ───────────────────────────────────────────────────────────────

interface EditModalProps {
  config: LLMConfig;
  providers: ProviderInfo[];
  token: string;
  onClose: () => void;
  onSaved: () => void;
}

function EditModal({ config, providers, token, onClose, onSaved }: EditModalProps) {
  const t = useTranslations("aiKeys");
  const provider = providers.find((p) => p.id === config.provider);
  const modelOptions = (provider?.models ?? []).map((m) => ({
    value: m,
    label: m,
  }));

  const [name, setName] = useState(config.name);
  const [nameError, setNameError] = useState("");
  const [model, setModel] = useState(config.model);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [showKeyInput, setShowKeyInput] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [rotating, setRotating] = useState(false);
  const [rotateError, setRotateError] = useState("");
  const [rotateSuccess, setRotateSuccess] = useState(false);

  async function handleSave() {
    const err = validateLLMConfigName(name);
    if (err) {
      setNameError(err);
      return;
    }

    setSaving(true);
    setSaveError("");
    try {
      await updateLLMConfig(token, config.id, { name, model });
      onSaved();
      onClose();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleRotateKey() {
    if (!newKey.trim()) return;

    setRotating(true);
    setRotateError("");
    setRotateSuccess(false);
    try {
      await rotateLLMConfigKey(token, config.id, newKey.trim());
      setRotateSuccess(true);
      setNewKey("");
      setShowKeyInput(false);
      onSaved();
    } catch (e) {
      setRotateError(e instanceof Error ? e.message : t("rotateError"));
    } finally {
      setRotating(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("editTitle")}</DialogTitle>
          <DialogDescription>{t("editDescription")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {saveError && <Alert severity="error">{saveError}</Alert>}

          <Input
            label={t("name")}
            name="name"
            value={name}
            error={nameError}
            onChange={(e) => {
              setName(e.target.value);
              setNameError(validateLLMConfigName(e.target.value));
            }}
            onBlur={() => setNameError(validateLLMConfigName(name))}
            placeholder={t("namePlaceholder")}
          />

          <div>
            <p className="block text-sm font-medium text-foreground mb-1.5">{t("provider")}</p>
            <p className="px-4 py-3 rounded-lg bg-surface-variant text-muted-foreground text-sm border-2 border-border">
              {provider?.label ?? config.provider}
              <span className="ml-2 text-xs text-muted-foreground">{t("providerLocked")}</span>
            </p>
          </div>

          <Select
            label={t("model")}
            value={model}
            options={modelOptions}
            onChange={(e) => setModel(e.target.value)}
            placeholder={t("modelPlaceholder")}
          />

          <div className="border-t border-border pt-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm font-medium text-foreground">{t("rotateTitle")}</p>
                <p className="text-xs text-muted-foreground">{t("rotateHint")}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowKeyInput((v) => !v);
                  setRotateError("");
                  setRotateSuccess(false);
                }}
              >
                <RotateCw className="h-4 w-4 mr-1.5" aria-hidden="true" />
                {t("rotate")}
              </Button>
            </div>

            {rotateSuccess && (
              <Alert severity="success" className="mb-3">
                {t("rotated")}
              </Alert>
            )}

            {rotateError && (
              <Alert severity="error" className="mb-3">
                {rotateError}
              </Alert>
            )}

            {showKeyInput && (
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder={t("newKeyPlaceholder")}
                  aria-label={t("newKeyPlaceholder")}
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  className="flex-1"
                />
                <Button
                  variant="primary"
                  size="sm"
                  loading={rotating}
                  spinnerLabel={t("saving")}
                  onClick={handleRotateKey}
                  disabled={!newKey.trim()}
                  aria-label={t("confirmRotation")}
                >
                  <Save className="h-4 w-4 mr-1.5" aria-hidden="true" />
                  {t("saveKey")}
                </Button>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            {t("cancel")}
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={saving}
            spinnerLabel={t("saving")}
            onClick={handleSave}
            disabled={!!validateLLMConfigName(name)}
          >
            {t("saveChanges")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Delete Confirmation Dialog ───────────────────────────────────────────────

interface DeleteDialogProps {
  config: LLMConfig;
  token: string;
  onClose: () => void;
  onDone: () => void;
}

function DeleteDialog({ config, token, onClose, onDone }: DeleteDialogProps) {
  const t = useTranslations("aiKeys");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleDelete() {
    setLoading(true);
    setError("");
    try {
      await deleteLLMConfig(token, config.id);
      onDone();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("deleteError"));
    } finally {
      setLoading(false);
    }
  }

  async function handleDeactivate() {
    setLoading(true);
    setError("");
    try {
      await setLLMConfigActive(token, config.id, false);
      onDone();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("deactivateError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("deleteTitle")}</DialogTitle>
          <DialogDescription>{t("deleteDescription")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {error && <Alert severity="error">{error}</Alert>}
          <p className="text-sm text-foreground">
            {t.rich("deleteConfirm", {
              name: config.name,
              b: (chunks) => <span className="font-semibold">{chunks}</span>,
            })}
          </p>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
            {t("cancel")}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            loading={loading}
            spinnerLabel={t("deactivating")}
            onClick={handleDeactivate}
          >
            {t("deactivate")}
          </Button>
          <Button
            variant="error"
            size="sm"
            loading={loading}
            spinnerLabel={t("deleting")}
            onClick={handleDelete}
          >
            {t("deleteAction")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Config Row ───────────────────────────────────────────────────────────────

interface ConfigRowProps {
  config: LLMConfig;
  token: string;
  onEdit: (config: LLMConfig) => void;
  onDelete: (config: LLMConfig) => void;
  onToggled: () => void;
}

function ConfigRow({ config, token, onEdit, onDelete, onToggled }: ConfigRowProps) {
  const t = useTranslations("aiKeys");
  return (
    <SettingsRow
      name={config.name}
      active={config.is_active}
      statusLabel={config.is_active ? t("active") : t("inactive")}
      badges={
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-50 text-secondary-700 dark:bg-secondary-900/30 dark:text-secondary-300">
          {config.provider}
        </span>
      }
      details={
        <>
          <span>{config.model}</span>
          <span className="font-mono">{config.masked_key}</span>
        </>
      }
      toggleLabel={t("toggle", { name: config.name })}
      onToggle={async (checked) => {
        await setLLMConfigActive(token, config.id, checked);
        onToggled();
      }}
      toggleErrorMessage={(e) => (e instanceof Error ? e.message : t("toggleError"))}
      actions={
        <>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit(config)}
            aria-label={t("edit", { name: config.name })}
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(config)}
            aria-label={t("delete", { name: config.name })}
            className="text-error-500 hover:text-error-600 hover:bg-error-50 dark:hover:bg-error-900/20"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </>
      }
    />
  );
}

// ─── New Config Modal ─────────────────────────────────────────────────────────

interface NewConfigModalProps {
  token: string;
  onClose: () => void;
  onCreated: () => void;
}

function NewConfigModal({ token, onClose, onCreated }: NewConfigModalProps) {
  const t = useTranslations("aiKeys");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");

  const [name, setName] = useState("");
  const [nameError, setNameError] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [apiKey, setApiKey] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    let ignore = false;
    fetchProviderCatalog(token)
      .then((catalog) => {
        if (ignore) return;
        setProviders(catalog.providers);
        if (catalog.default_provider) {
          setSelectedProvider(catalog.default_provider);
          const info = catalog.providers.find((p) => p.id === catalog.default_provider);
          setSelectedModel(catalog.default_model || info?.models?.[0] || "");
        } else if (catalog.providers.length > 0) {
          setSelectedProvider(catalog.providers[0].id);
          setSelectedModel(catalog.providers[0].models[0] ?? "");
        }
      })
      .catch((e) => {
        if (!ignore) setCatalogError(e instanceof Error ? e.message : t("catalogError"));
      })
      .finally(() => {
        if (!ignore) setCatalogLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [token]);

  function handleProviderChange(providerId: string) {
    setSelectedProvider(providerId);
    const info = providers.find((p) => p.id === providerId);
    setSelectedModel(info?.models?.[0] ?? "");
  }

  const currentProviderInfo = providers.find((p) => p.id === selectedProvider);
  const modelOptions = (currentProviderInfo?.models ?? []).map((m) => ({
    value: m,
    label: m,
  }));
  const providerOptions = providers.map((p) => ({
    value: p.id,
    label: p.label,
  }));

  const formValid =
    !catalogError &&
    !validateLLMConfigName(name) &&
    name.trim().length > 0 &&
    selectedProvider !== "" &&
    selectedModel !== "" &&
    apiKey.trim() !== "";

  async function handleSubmit() {
    const nameErr = validateLLMConfigName(name);
    if (nameErr) {
      setNameError(nameErr);
      return;
    }
    if (!selectedProvider || !selectedModel || !apiKey.trim()) return;

    setSubmitting(true);
    setSubmitError("");
    try {
      await createLLMConfig(token, {
        name: name.trim(),
        provider: selectedProvider,
        model: selectedModel,
        api_key: apiKey.trim(),
      });
      onCreated();
      onClose();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : t("createError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("newTitle")}</DialogTitle>
          <DialogDescription>{t("newDescription")}</DialogDescription>
        </DialogHeader>

        {catalogLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spinner />
          </div>
        ) : (
          <form
            aria-label={t("newFormLabel")}
            onSubmit={(e) => {
              e.preventDefault();
              void handleSubmit();
            }}
            noValidate
          >
            <div className="space-y-4">
              {catalogError && <Alert severity="error">{catalogError}</Alert>}
              {submitError && <Alert severity="error">{submitError}</Alert>}

              <Input
                label={t("name")}
                name="name"
                required
                placeholder={t("namePlaceholder")}
                value={name}
                error={nameError}
                autoFocus
                onChange={(e) => {
                  setName(e.target.value);
                  setNameError(validateLLMConfigName(e.target.value));
                }}
                onBlur={(e) => setNameError(validateLLMConfigName(e.target.value))}
                disabled={submitting || !!catalogError}
              />

              <Select
                label={t("provider")}
                name="provider"
                required
                placeholder={t("providerPlaceholder")}
                value={selectedProvider}
                options={providerOptions}
                onChange={(e) => handleProviderChange(e.target.value)}
                disabled={submitting || !!catalogError || providers.length === 0}
              />

              <div aria-live="polite">
                <Select
                  label={t("model")}
                  name="model"
                  required
                  placeholder={t("modelPlaceholder")}
                  value={selectedModel}
                  options={modelOptions}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  disabled={
                    submitting || !!catalogError || !selectedProvider || modelOptions.length === 0
                  }
                />
              </div>

              <Input
                label={t("apiKey")}
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

            <DialogFooter className="mt-6">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onClose}
                disabled={submitting}
              >
                {t("cancel")}
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                loading={submitting}
                spinnerLabel={t("creating")}
                disabled={!formValid || submitting}
              >
                {t("create")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LLMConfigurePage() {
  const t = useTranslations("aiKeys");
  const { token } = useAuth();

  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showNewModal, setShowNewModal] = useState(false);
  const [editingConfig, setEditingConfig] = useState<LLMConfig | null>(null);
  const [deletingConfig, setDeletingConfig] = useState<LLMConfig | null>(null);

  const loadData = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const [configsResult, providersResult] = await Promise.all([
        fetchLLMConfigs(token, { includeInactive: true }),
        fetchProviderCatalog(token),
      ]);
      setConfigs(configsResult.configs);
      setProviders(providersResult.providers);
      setEditingConfig((prev) =>
        prev ? (configsResult.configs.find((c) => c.id === prev.id) ?? null) : null,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("loadError"));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (!loading && !token) return null;

  return (
    <SettingsPage
      title={t("title")}
      subtitle={t("subtitle")}
      loading={loading}
      loadingLabel={t("loading")}
      error={error}
      actions={
        <Button variant="primary" size="sm" onClick={() => setShowNewModal(true)}>
          <Plus className="h-4 w-4 mr-1.5" aria-hidden="true" />
          {t("newConfig")}
        </Button>
      }
    >
      {token && (
        <>
          <SettingsList
            empty={
              <>
                <KeyRound
                  className="mx-auto mb-4 h-10 w-10 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-muted-foreground mb-4">{t("empty")}</p>
                <Button variant="primary" size="sm" onClick={() => setShowNewModal(true)}>
                  <Plus className="h-4 w-4 mr-1.5" aria-hidden="true" />
                  {t("createFirst")}
                </Button>
              </>
            }
          >
            {configs.map((config) => (
              <ConfigRow
                key={config.id}
                config={config}
                token={token}
                onEdit={setEditingConfig}
                onDelete={setDeletingConfig}
                onToggled={loadData}
              />
            ))}
          </SettingsList>

          {showNewModal && (
            <NewConfigModal
              token={token}
              onClose={() => setShowNewModal(false)}
              onCreated={loadData}
            />
          )}

          {editingConfig && (
            <EditModal
              config={editingConfig}
              providers={providers}
              token={token}
              onClose={() => setEditingConfig(null)}
              onSaved={loadData}
            />
          )}

          {deletingConfig && (
            <DeleteDialog
              config={deletingConfig}
              token={token}
              onClose={() => setDeletingConfig(null)}
              onDone={loadData}
            />
          )}
        </>
      )}
    </SettingsPage>
  );
}
