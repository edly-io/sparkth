"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import type { UserPluginState } from "@/lib/plugins";

interface SlackConfigModalProps {
  plugin: UserPluginState;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (config: Record<string, unknown>) => Promise<void>;
  onRefresh: () => void;
}

export default function SlackConfigModal({ plugin, open, onOpenChange }: SlackConfigModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configure {plugin.plugin_name}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground py-4">Bot configuration coming soon.</p>
      </DialogContent>
    </Dialog>
  );
}
