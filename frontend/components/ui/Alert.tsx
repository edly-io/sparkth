import { HTMLAttributes, forwardRef } from "react";
import { X } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva("rounded-lg p-4 flex items-start gap-3", {
  variants: {
    severity: {
      error: "bg-error-50 text-error-700 dark:bg-error-900/30 dark:text-error-300",
      warning: "bg-warning-50 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300",
      success: "bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300",
      info: "bg-secondary-50 text-secondary-700 dark:bg-secondary-900/30 dark:text-secondary-300",
    },
  },
  defaultVariants: {
    severity: "info",
  },
});

interface AlertProps extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof alertVariants> {
  title?: string;
  onClose?: () => void;
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, severity, title, children, onClose, ...props }, ref) => {
    return (
      <div ref={ref} className={cn(alertVariants({ severity }), className)} role="alert" {...props}>
        <div className="flex justify-between items-start gap-4 w-full">
          <div className="flex-1">
            {title && <p className="font-semibold mb-1">{title}</p>}
            <div className="text-sm">{children}</div>
          </div>

          {onClose && (
            <button
              onClick={onClose}
              aria-label="Dismiss alert"
              className="
                p-1 rounded-md
                opacity-60 hover:opacity-100
                hover:bg-black/5 dark:hover:bg-white/10
                transition
              "
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    );
  },
);

Alert.displayName = "Alert";
