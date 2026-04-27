"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Mail, Globe } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  getWhitelist,
  addWhitelistEntry,
  removeWhitelistEntry,
  WhitelistEntry,
  ApiRequestError,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/Spinner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";

export default function WhitelistPage() {
  const { token, user } = useAuth();
  const router = useRouter();

  const [entries, setEntries] = useState<WhitelistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newValue, setNewValue] = useState("");
  const [addError, setAddError] = useState("");
  const [adding, setAdding] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<WhitelistEntry | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (user && !user.is_superuser) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  const fetchEntries = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getWhitelist(token);
      setEntries(data);
      setError("");
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Failed to load whitelist");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !newValue.trim()) return;

    setAdding(true);
    setAddError("");

    try {
      await addWhitelistEntry(token, newValue.trim());
      setNewValue("");
      await fetchEntries();
    } catch (err) {
      setAddError(err instanceof ApiRequestError ? err.message : "Failed to add entry");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async () => {
    if (!token || !deleteTarget) return;

    setDeleting(true);
    try {
      await removeWhitelistEntry(token, deleteTarget.id);
      setDeleteTarget(null);
      await fetchEntries();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Failed to remove entry");
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  };

  if (user && !user.is_superuser) return null;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">Loading whitelist...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Email Whitelist</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Manage which email addresses and domains are allowed to register. Only whitelisted
            entries can create accounts.
          </p>
        </div>

        {error && (
          <Alert severity="error" className="mb-4">
            {error}
          </Alert>
        )}

        <form onSubmit={handleAdd} className="flex gap-3 mb-6">
          <div className="flex-1">
            <Input
              name="whitelist-value"
              type="text"
              placeholder="Email (user@example.com) or domain (@example.com)"
              value={newValue}
              onChange={(e) => {
                setNewValue(e.target.value);
                setAddError("");
              }}
              error={addError}
            />
          </div>
          <Button type="submit" loading={adding} disabled={!newValue.trim()} spinnerLabel="Adding">
            <Plus className="w-4 h-4 mr-1" />
            Add
          </Button>
        </form>

        {entries.length > 0 ? (
          <div className="bg-card rounded-lg shadow-sm overflow-hidden border border-border">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-surface-variant/50">
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                    Value
                  </th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                    Type
                  </th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground hidden sm:table-cell">
                    Added
                  </th>
                  <th className="w-12 px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id} className="border-b border-border last:border-b-0">
                    <td className="px-4 py-3 text-sm text-foreground font-mono">{entry.value}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                          entry.entry_type === "domain"
                            ? "bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300"
                            : "bg-success-100 text-success-700 dark:bg-success-900/30 dark:text-success-300"
                        }`}
                      >
                        {entry.entry_type === "domain" ? (
                          <Globe className="w-3 h-3" />
                        ) : (
                          <Mail className="w-3 h-3" />
                        )}
                        {entry.entry_type === "domain" ? "Domain" : "Email"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground hidden sm:table-cell">
                      {new Date(entry.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(entry)}
                        aria-label={`Remove ${entry.value}`}
                        className="text-error-500 hover:text-error-700 hover:bg-error-50 dark:hover:bg-error-900/30"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
            <Mail className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
            <p className="text-muted-foreground">
              No whitelisted emails yet. Add an email or domain to allow registration.
            </p>
          </div>
        )}
      </div>

      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Remove whitelist entry</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove{" "}
              <span className="font-mono font-medium text-foreground">{deleteTarget?.value}</span>?
              {deleteTarget?.entry_type === "domain"
                ? " Users from this domain will no longer be able to register."
                : " This email will no longer be able to register."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting}>
              Cancel
            </Button>
            <Button
              variant="error"
              onClick={handleDelete}
              loading={deleting}
              spinnerLabel="Removing"
            >
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
