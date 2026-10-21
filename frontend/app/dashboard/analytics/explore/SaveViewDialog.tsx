"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ApiRequestError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";

/**
 * Asks for a view name and calls `onSave` with it, trimmed; stays open with a message when the
 * name is taken or saving fails.
 */
export function SaveViewDialog({
  open,
  title,
  initialName = "",
  onSave,
  onClose,
}: {
  open: boolean;
  title: string;
  initialName?: string;
  onSave: (name: string) => Promise<void>;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md" aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        {/* Mounted per opening, so the form starts fresh each time. */}
        <NameForm initialName={initialName} onSave={onSave} onClose={onClose} />
      </DialogContent>
    </Dialog>
  );
}

function NameForm({
  initialName,
  onSave,
  onClose,
}: {
  initialName: string;
  onSave: (name: string) => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("analytics.explore");
  const [name, setName] = useState(initialName);
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(name.trim());
      onClose();
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 409) {
        setError(t("nameTaken"));
      } else {
        console.error("Saving the analytics view failed:", err);
        setError(t("saveError"));
      }
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <Input
        id="explore-view-name"
        label={t("viewName")}
        value={name}
        maxLength={100}
        error={error}
        onChange={(e) => setName(e.target.value)}
        autoFocus
      />
      <DialogFooter>
        <Button type="submit" loading={saving} disabled={!name.trim()}>
          {t("save")}
        </Button>
      </DialogFooter>
    </form>
  );
}
