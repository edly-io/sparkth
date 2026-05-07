"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { KeyRound, Pencil, Plus, RotateCw, Save, Trash2 } from "lucide-react";

import { Spinner } from "@/components/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
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
import { Switch } from "@/components/ui/Switch";
import { useAuth } from "@/lib/auth-context";
import {
  deleteLLMConfig,
  fetchLLMConfigs,
  fetchProviderCatalog,
  rotateLLMConfigKey,
  setLLMConfigActive,
  updateLLMConfig,
  type LLMConfig,
  type ProviderInfo,
} from "@/lib/llm-api";

// ─── Name validation ─────────────────────────────────────────────────────────

const NAME_PATTERN = /^[a-zA-Z0-9_-]+$/;

function validateName(value: string): string {
  if (!value.trim()) return "Name is required";
  if (!NAME_PATTERN.test(value)) return "Only letters, numbers, hyphens, and underscores allowed";
  return "";
}

// ─── Edit Modal ───────────────────────────────────────────────────────────────

interface EditModalProps {
  config: LLMConfig;
  providers: ProviderInfo[];
  token: string;
  onClose: () => void;
  onSaved: () => void;
}

function EditModal({ config, providers, token, onClose, onSaved }: EditModalProps) {
  const provider = providers.find((p) => p.id === config.provider);
  const modelOptions = (provider?.models ?? []).map((m) => ({ value: m, label: m }));

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
    const err = validateName(name);
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
      setSaveError(e instanceof Error ? e.message : "Failed to save changes");
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
      setRotateError(e instanceof Error ? e.message : "Failed to rotate API key");
    } finally {
      setRotating(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Config</DialogTitle>
          <DialogDescription>
            Update the name, model, or API key for this configuration.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {saveError && <Alert severity="error">{saveError}</Alert>}

          <Input
            label="Name"
            value={name}
            error={nameError}
            onChange={(e) => {
              setName(e.target.value);
              if (nameError) setNameError(validateName(e.target.value));
            }}
            onBlur={() => setNameError(validateName(name))}
            placeholder="e.g. my-openai-key"
          />

          <div>
            <p className="block text-sm font-medium text-foreground mb-1.5">Provider</p>
            <p className="px-4 py-3 rounded-lg bg-surface-variant text-muted-foreground text-sm border-2 border-border">
              {provider?.label ?? config.provider}
              <span className="ml-2 text-xs text-muted-foreground">(cannot be changed)</span>
            </p>
          </div>

          <Select
            label="Model"
            value={model}
            options={modelOptions}
            onChange={(e) => setModel(e.target.value)}
            placeholder="Select a model"
          />

          <div className="border-t border-border pt-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm font-medium text-foreground">Rotate API Key</p>
                <p className="text-xs text-muted-foreground">
                  Replace the stored key with a new one
                </p>
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
                Rotate Key
              </Button>
            </div>

            {rotateSuccess && (
              <Alert severity="success" className="mb-3">
                API key rotated successfully.
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
                  placeholder="New API key"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  className="flex-1"
                />
                <Button
                  variant="primary"
                  size="sm"
                  loading={rotating}
                  spinnerLabel="Saving"
                  onClick={handleRotateKey}
                  disabled={!newKey.trim()}
                  aria-label="Confirm key rotation"
                >
                  <Save className="h-4 w-4 mr-1.5" aria-hidden="true" />
                  Save Key
                </Button>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={saving}
            spinnerLabel="Saving"
            onClick={handleSave}
          >
            Save Changes
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
      setError(e instanceof Error ? e.message : "Failed to delete config");
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
      setError(e instanceof Error ? e.message : "Failed to deactivate config");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Config</DialogTitle>
          <DialogDescription>
            This action cannot be undone. Plugins using this config will lose access.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {error && <Alert severity="error">{error}</Alert>}
          <p className="text-sm text-foreground">
            Are you sure you want to delete <span className="font-semibold">{config.name}</span>?
            Plugins using this config will lose access. Consider deactivating it instead if you
            might need it later.
          </p>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant="secondary"
            size="sm"
            loading={loading}
            spinnerLabel="Deactivating"
            onClick={handleDeactivate}
          >
            Deactivate
          </Button>
          <Button
            variant="error"
            size="sm"
            loading={loading}
            spinnerLabel="Deleting"
            onClick={handleDelete}
          >
            Delete
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
  onError: (message: string) => void;
  isLast: boolean;
}

function ConfigRow({
  config,
  token,
  onEdit,
  onDelete,
  onToggled,
  onError,
  isLast,
}: ConfigRowProps) {
  const [toggling, setToggling] = useState(false);

  async function handleToggle(checked: boolean) {
    setToggling(true);
    try {
      await setLLMConfigActive(token, config.id, checked);
      onToggled();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Failed to toggle config");
    } finally {
      setToggling(false);
    }
  }

  return (
    <div
      role="listitem"
      className={`flex flex-col sm:flex-row sm:items-center gap-3 px-4 py-4 ${!isLast ? "border-b border-border" : ""}`}
    >
      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className="font-medium text-foreground truncate">{config.name}</span>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-50 text-secondary-700 dark:bg-secondary-900/30 dark:text-secondary-300">
            {config.provider}
          </span>
          <span
            aria-label={config.is_active ? "Active" : "Inactive"}
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
              config.is_active
                ? "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300"
                : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400"
            }`}
          >
            {config.is_active ? "Active" : "Inactive"}
          </span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-muted-foreground">
          <span>{config.model}</span>
          <span className="font-mono">{config.masked_key}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 shrink-0">
        <Switch
          checked={config.is_active}
          onCheckedChange={handleToggle}
          disabled={toggling}
          aria-label={`Toggle active status for ${config.name}`}
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onEdit(config)}
          aria-label={`Edit config ${config.name}`}
        >
          <Pencil className="h-4 w-4" aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete(config)}
          aria-label={`Delete config ${config.name}`}
          className="text-error-500 hover:text-error-600 hover:bg-error-50 dark:hover:bg-error-900/20"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LLMConfigurePage() {
  const { token } = useAuth();

  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
        fetchLLMConfigs(token),
        fetchProviderCatalog(token),
      ]);
      setConfigs(configsResult.configs);
      setProviders(providersResult.providers);
      setEditingConfig((prev) =>
        prev ? (configsResult.configs.find((c) => c.id === prev.id) ?? null) : null,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load LLM configs");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">Loading LLM configs...</p>
        </div>
      </div>
    );
  }

  if (!token) return null;

  if (error) {
    return (
      <div className="min-h-screen bg-background">
        <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
          <Alert severity="error">{error}</Alert>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6 sm:mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">AI Keys</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Manage API keys and model configurations for connected LLM providers.
            </p>
          </div>
          <Button variant="primary" size="sm" asChild>
            <Link href="/dashboard/llm/configure/new/">
              <Plus className="h-4 w-4 mr-1.5" aria-hidden="true" />
              New Config
            </Link>
          </Button>
        </div>

        {/* List */}
        {configs.length > 0 ? (
          <div
            role="list"
            className="bg-card rounded-lg shadow-sm overflow-hidden border border-border"
          >
            {configs.map((config, index) => (
              <ConfigRow
                key={config.id}
                config={config}
                token={token}
                onEdit={setEditingConfig}
                onDelete={setDeletingConfig}
                onToggled={loadData}
                onError={setError}
                isLast={index === configs.length - 1}
              />
            ))}
          </div>
        ) : (
          <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
            <KeyRound className="mx-auto mb-4 h-10 w-10 text-muted-foreground" aria-hidden="true" />
            <p className="text-muted-foreground mb-4">No LLM configs found.</p>
            <Button variant="primary" size="sm" asChild>
              <Link href="/dashboard/llm/configure/new/">
                <Plus className="h-4 w-4 mr-1.5" aria-hidden="true" />
                Create Your First Config
              </Link>
            </Button>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingConfig && (
        <EditModal
          config={editingConfig}
          providers={providers}
          token={token}
          onClose={() => setEditingConfig(null)}
          onSaved={loadData}
        />
      )}

      {/* Delete Dialog */}
      {deletingConfig && (
        <DeleteDialog
          config={deletingConfig}
          token={token}
          onClose={() => setDeletingConfig(null)}
          onDone={loadData}
        />
      )}
    </div>
  );
}
