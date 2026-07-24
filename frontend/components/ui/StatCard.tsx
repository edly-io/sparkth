import { HTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/Card";

interface StatCardProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  value: string | number;
  hint?: string;
}

// A single-metric tile composed on the existing Card primitive.
export const StatCard = forwardRef<HTMLDivElement, StatCardProps>(
  ({ title, value, hint, className, ...props }, ref) => {
    return (
      <Card
        ref={ref}
        variant="outlined"
        className={cn("flex flex-col gap-1", className)}
        {...props}
      >
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <p className="text-3xl font-bold text-foreground">{value}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </Card>
    );
  },
);

StatCard.displayName = "StatCard";
