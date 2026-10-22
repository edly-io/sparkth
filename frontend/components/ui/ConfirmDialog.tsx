"use client";

import { useState } from "react";

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

/**
 * A dialog that asks before running an action, such as a delete.
 *
 * While `onConfirm` runs, both buttons are disabled and the dialog cannot be dismissed. If it
 * rejects, the error is logged and the dialog stays open showing `errorMessage`. On success the
 * caller closes the dialog, usually by unmounting it.
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
  const [failed, setFailed] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    setFailed(false);
    try {
      await onConfirm();
    } catch (error) {
      console.error("ConfirmDialog: action failed", error);
      setFailed(true);
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

        {failed && <Alert severity="error">{errorMessage}</Alert>}

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
