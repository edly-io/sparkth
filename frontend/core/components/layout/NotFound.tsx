import type { ReactNode } from "react";
import { SearchX } from "lucide-react";
import { MessagePanel } from "@/core/components/layout/MessagePanel";

interface NotFoundProps {
  title: string;
  message?: string;
  action?: ReactNode;
}

/**
 * A panel shown in place of something a URL names that does not exist, announced to screen readers
 * when it appears.
 *
 * Has no text of its own: the caller passes its translated title, an optional message and an
 * optional action, such as a link to somewhere that does exist.
 */
export function NotFound({ title, message, action }: NotFoundProps): React.JSX.Element {
  return (
    <div role="alert">
      <MessagePanel icon={SearchX} title={title} message={message} action={action} />
    </div>
  );
}
