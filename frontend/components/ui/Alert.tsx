import { HTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva("rounded-lg p-4 flex items-start gap-3", {
  variants: {
    severity: {
      error:
        "bg-error-50 text-error-700 dark:bg-error-900/30 dark:text-error-300",
      warning:
        "bg-warning-50 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300",
      success:
        "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300",
      info: "bg-secondary-50 text-secondary-700 dark:bg-secondary-900/30 dark:text-secondary-300",
    },
  },
  defaultVariants: {
    severity: "info",
  },
});

interface AlertProps
  extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof alertVariants> {
  title?: string;
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, severity, title, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(alertVariants({ severity }), className)}
        role="alert"
        {...props}
      >
        <div>
          {title && <p className="font-semibold mb-1">{title}</p>}
          <p className="text-sm">{children}</p>
        </div>
      </div>
    );
  },
);

Alert.displayName = "Alert";
