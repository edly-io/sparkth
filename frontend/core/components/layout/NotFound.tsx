import type { ReactNode } from "react";
import { SearchX } from "lucide-react";

interface NotFoundProps {
  title: string;
  message?: string;
  action?: ReactNode;
}

/**
 * A page for something a URL names that does not exist, centred in the area it is placed in.
 *
 * Has no text of its own: the caller passes its translated title, an optional message and an
 * optional action, such as a link to somewhere that does exist.
 */
export function NotFound({ title, message, action }: NotFoundProps): React.JSX.Element {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-md text-center">
        <SearchX className="mx-auto mb-4 h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <h2 className="mb-2 text-lg font-semibold text-foreground">{title}</h2>
        {message && <p className="mb-4 text-muted-foreground">{message}</p>}
        {action}
      </div>
    </div>
  );
}
