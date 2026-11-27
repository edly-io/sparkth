"use client";

import { useEffect, useState } from "react";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/core/auth/hooks";
import { getRole, setRolePermissions } from "@/core/permissions/client";
import type { RoleResponse } from "@/core/permissions/types";

type SaveStatus = "idle" | "saving" | "saved" | "failed";

/** How long "Saved" shows after a save, in milliseconds. */
const SAVED_MESSAGE_MS = 3000;

/**
 * A loaded role. `checked` starts as every permission the role holds, including any that is no
 * longer declared, so saving keeps those. `saveStatus` says where saving the checked ones stands.
 */
type LoadedRole = {
  status: "loaded";
  role: RoleResponse;
  checked: ReadonlySet<string>;
  saveStatus: SaveStatus;
};

type RoleState = { status: "loading" | "missing" | "failed" } | LoadedRole;

/** A role's page: the role, the permissions checked on it, and saving them. */
export interface RoleEditor {
  /** The role once loaded; "missing" when there is no such role, "failed" when loading fails. */
  state: RoleState;
  /** Whether the permissions checked differ from the ones the role holds. */
  changed: boolean;
  /** Checks exactly `checked`, clearing what the last save reported. */
  setChecked: (checked: ReadonlySet<string>) => void;
  /**
   * Saves the permissions checked and shows the saved role, reporting the outcome as `saveStatus`:
   * "saved" for a few seconds, or "failed" with the checked ones kept.
   */
  saveChecked: () => Promise<void>;
}

/**
 * Loads the role `roleId` with its own permissions checked, and saves the ones checked since.
 * There is no such role when `roleId` is null.
 */
export function useRoleEditor(roleId: number | null): RoleEditor {
  const { token } = useAuth();
  const [state, setState] = useState<RoleState>({ status: "loading" });

  useEffect(() => {
    if (roleId === null) {
      setState({ status: "missing" });
      return;
    }
    setState({ status: "loading" });
    if (!token) return;
    let active = true;
    getRole(token, roleId)
      .then((role) => {
        if (active) setState(getLoadedState(role, "idle"));
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiRequestError && error.status === 404) {
          setState({ status: "missing" });
          return;
        }
        console.error("Loading the role failed:", error);
        setState({ status: "failed" });
      });
    return () => {
      active = false;
    };
  }, [token, roleId]);

  const saveStatus = state.status === "loaded" ? state.saveStatus : "idle";
  useEffect(() => {
    if (saveStatus !== "saved") return;
    const timer = setTimeout(
      () =>
        setState((current) =>
          current.status === "loaded" && current.saveStatus === "saved"
            ? { ...current, saveStatus: "idle" }
            : current,
        ),
      SAVED_MESSAGE_MS,
    );
    return () => clearTimeout(timer);
  }, [saveStatus]);

  // Applies `next` only while the role `shownRoleId` is still on show, so a save finishing after
  // another role was opened changes nothing.
  const updateRole = (shownRoleId: number, next: (current: LoadedRole) => LoadedRole) =>
    setState((current) =>
      current.status === "loaded" && current.role.id === shownRoleId ? next(current) : current,
    );

  const setChecked = (checked: ReadonlySet<string>) => {
    if (state.status !== "loaded") throw new Error("The role is not loaded");
    setState({ ...state, checked, saveStatus: "idle" });
  };

  const saveChecked = async () => {
    if (state.status !== "loaded") throw new Error("The role is not loaded");
    const { role, checked } = state;
    setState({ ...state, saveStatus: "saving" });
    try {
      if (!token) throw new Error("not signed in");
      const savedRole = await setRolePermissions(token, role.id, [...checked]);
      updateRole(role.id, () => getLoadedState(savedRole, "saved"));
    } catch (error) {
      console.error("Saving the role's permissions failed:", error);
      updateRole(role.id, (current) => ({ ...current, saveStatus: "failed" }));
    }
  };

  return {
    state,
    changed: state.status === "loaded" && hasChanges(state),
    setChecked,
    saveChecked,
  };
}

/** A role just loaded or saved: every permission it holds checked, and `saveStatus` as given. */
function getLoadedState(role: RoleResponse, saveStatus: SaveStatus): LoadedRole {
  return { status: "loaded", role, checked: new Set(role.permissions), saveStatus };
}

/** Whether the permissions checked differ from the ones the role holds. */
function hasChanges({ role, checked }: LoadedRole): boolean {
  const held = new Set(role.permissions);
  return checked.size !== held.size || [...checked].some((permission) => !held.has(permission));
}
