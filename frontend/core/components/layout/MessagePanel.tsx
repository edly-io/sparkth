import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

interface MessagePanelProps {
  icon: LucideIcon;
  title: string;
  message?: string;
  action?: ReactNode;
}

/**
 * A card that fills a page area with an icon, a title, an optional message and an optional action.
 *
 * Has no text of its own: the caller passes the translated text, and the icon that tells the
 * situation apart.
 */
export function MessagePanel({
  icon: Icon,
  title,
  message,
  action,
}: MessagePanelProps): React.JSX.Element {
  return (
    <div className="bg-card rounded-lg border border-border p-12 text-center">
      <Icon className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" aria-hidden="true" />
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      {message && <p className="mt-2 text-muted-foreground">{message}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
