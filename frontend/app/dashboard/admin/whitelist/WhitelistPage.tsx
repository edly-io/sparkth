"use client";

import { useReducer, useEffect, useCallback } from "react";
import { redirect } from "next/navigation";
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

interface WhitelistState {
  entries: WhitelistEntry[];
  loading: boolean;
  error: string;
  newValue: string;
  addError: string;
  adding: boolean;
  deleteTarget: WhitelistEntry | null;
  deleting: boolean;
}

type WhitelistAction =
  | { type: "SET_ENTRIES"; entries: WhitelistEntry[] }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "SET_ERROR"; error: string }
  | { type: "SET_NEW_VALUE"; value: string }
  | { type: "SET_ADD_ERROR"; error: string }
  | { type: "SET_ADDING"; adding: boolean }
  | { type: "SET_DELETE_TARGET"; target: WhitelistEntry | null }
  | { type: "SET_DELETING"; deleting: boolean };

function reducer(state: WhitelistState, action: WhitelistAction): WhitelistState {
  switch (action.type) {
    case "SET_ENTRIES":
      return { ...state, entries: action.entries, error: "" };
    case "SET_LOADING":
      return { ...state, loading: action.loading };
    case "SET_ERROR":
      return { ...state, error: action.error };
    case "SET_NEW_VALUE":
      return { ...state, newValue: action.value, addError: "" };
    case "SET_ADD_ERROR":
      return { ...state, addError: action.error };
    case "SET_ADDING":
      return { ...state, adding: action.adding };
    case "SET_DELETE_TARGET":
      return { ...state, deleteTarget: action.target };
    case "SET_DELETING":
      return { ...state, deleting: action.deleting };
  }
}

const initialState: WhitelistState = {
  entries: [],
  loading: true,
  error: "",
  newValue: "",
  addError: "",
  adding: false,
  deleteTarget: null,
  deleting: false,
};

export default function WhitelistPage() {
  const { token, user } = useAuth();
  const [state, dispatch] = useReducer(reducer, initialState);

  if (user && !user.is_superuser) {
    redirect("/dashboard");
  }

  const fetchEntries = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getWhitelist(token);
      dispatch({ type: "SET_ENTRIES", entries: data });
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        error: err instanceof ApiRequestError ? err.message : "Failed to load whitelist",
      });
    } finally {
      dispatch({ type: "SET_LOADING", loading: false });
    }
  }, [token]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !state.newValue.trim()) return;

    dispatch({ type: "SET_ADDING", adding: true });
    dispatch({ type: "SET_ADD_ERROR", error: "" });

    try {
      await addWhitelistEntry(token, state.newValue.trim());
      dispatch({ type: "SET_NEW_VALUE", value: "" });
      await fetchEntries();
    } catch (err) {
      dispatch({
        type: "SET_ADD_ERROR",
        error: err instanceof ApiRequestError ? err.message : "Failed to add entry",
      });
    } finally {
      dispatch({ type: "SET_ADDING", adding: false });
    }
  };

  const handleDelete = async () => {
    if (!token || !state.deleteTarget) return;

    dispatch({ type: "SET_DELETING", deleting: true });
    try {
      await removeWhitelistEntry(token, state.deleteTarget.id);
      dispatch({ type: "SET_DELETE_TARGET", target: null });
      await fetchEntries();
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        error: err instanceof ApiRequestError ? err.message : "Failed to remove entry",
      });
      dispatch({ type: "SET_DELETE_TARGET", target: null });
    } finally {
      dispatch({ type: "SET_DELETING", deleting: false });
    }
  };

  if (state.loading) {
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

        {state.error && (
          <Alert severity="error" className="mb-4">
            {state.error}
          </Alert>
        )}

        <form onSubmit={handleAdd} className="flex gap-3 mb-6">
          <div className="flex-1">
            <Input
              name="whitelist-value"
              type="text"
              placeholder="Email (user@example.com) or domain (@example.com)"
              value={state.newValue}
              onChange={(e) => dispatch({ type: "SET_NEW_VALUE", value: e.target.value })}
              error={state.addError}
            />
          </div>
          <Button
            type="submit"
            loading={state.adding}
            disabled={!state.newValue.trim()}
            spinnerLabel="Adding"
          >
            <Plus className="w-4 h-4 mr-1" />
            Add
          </Button>
        </form>

        {state.entries.length > 0 ? (
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
                {state.entries.map((entry) => (
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
                        onClick={() => dispatch({ type: "SET_DELETE_TARGET", target: entry })}
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

      <Dialog
        open={!!state.deleteTarget}
        onOpenChange={() => dispatch({ type: "SET_DELETE_TARGET", target: null })}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Remove whitelist entry</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove{" "}
              <span className="font-mono font-medium text-foreground">
                {state.deleteTarget?.value}
              </span>
              ?
              {state.deleteTarget?.entry_type === "domain"
                ? " Users from this domain will no longer be able to register."
                : " This email will no longer be able to register."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => dispatch({ type: "SET_DELETE_TARGET", target: null })}
              disabled={state.deleting}
            >
              Cancel
            </Button>
            <Button
              variant="error"
              onClick={handleDelete}
              loading={state.deleting}
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
