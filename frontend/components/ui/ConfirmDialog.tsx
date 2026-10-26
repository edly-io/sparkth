"use client";

import { useState } from "react";

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
import { ApiRequestError } from "@/lib/api";

/**
 * A dialog that asks before running an action, such as a delete.
 *
 * While `onConfirm` runs, both buttons are disabled and the dialog cannot be dismissed. If it
 * rejects, the error is logged and the dialog stays open showing the message of an
 * `ApiRequestError`, or `errorMessage` for any other error. On success the caller closes the
 * dialog, usually by unmounting it.
 */
export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  pendingLabel,
  cancelLabel,
  errorMessage,
  onConfirm,
  onClose,
}: {
  title: string;
  description: React.ReactNode;
  confirmLabel: string;
  pendingLabel: string;
  cancelLabel: string;
  errorMessage: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}): React.JSX.Element {
  const [loading, setLoading] = useState(false);
  const [shownError, setShownError] = useState<string | null>(null);

  async function handleConfirm() {
    setLoading(true);
    setShownError(null);
    try {
      await onConfirm();
    } catch (error) {
      console.error("ConfirmDialog: action failed", error);
      setShownError(error instanceof ApiRequestError ? error.message : errorMessage);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !loading && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {shownError && <Alert severity="error">{shownError}</Alert>}

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant="error"
            size="sm"
            loading={loading}
            spinnerLabel={pendingLabel}
            disabled={loading}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
