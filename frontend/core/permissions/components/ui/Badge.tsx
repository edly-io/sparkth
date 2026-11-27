import type { ReactNode } from "react";
import { twMerge } from "tailwind-merge";

/** A small pill label; `className` gives it its colours. */
export function Badge({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span
      className={twMerge(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}
