import { HTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "elevated" | "outlined" | "filled";
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "elevated", children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-xl p-6",
          {
            elevated: "bg-card text-card-foreground shadow-lg",
            outlined: "bg-card text-card-foreground border border-border",
            filled: "bg-surface-variant text-foreground",
          }[variant],
          className,
        )}
        {...props}
      >
        {children}
      </div>
    );
  },
);

Card.displayName = "Card";
