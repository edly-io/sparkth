import { Check, Minus } from "lucide-react";

/** A tick for granted, a dash for not. Decorative: say which in words beside it. */
export function GrantStatusIcon({ granted }: { granted: boolean }) {
  return granted ? (
    <Check className="h-4 w-4 text-primary-600" aria-hidden="true" />
  ) : (
    <Minus className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
  );
}
