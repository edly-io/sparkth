"use client";

import { type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export function Textarea({
  id,
  label,
  error,
  helperText,
  className,
  required,
  "aria-describedby": ariaDescribedBy,
  ...props
}: TextareaProps) {
  const errorId = error && id ? `${id}-error` : undefined;
  const helperId = helperText && !error && id ? `${id}-helper` : undefined;
  const describedBy = [ariaDescribedBy, errorId, helperId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-foreground mb-1.5">
          {label}
          {required && (
            <span className="text-error-500 ml-0.5" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}
      <textarea
        id={id}
        required={required}
        aria-describedby={describedBy}
        aria-invalid={error ? true : undefined}
        rows={3}
        className={cn(
          "block w-full px-4 py-3 rounded-lg",
          "placeholder-muted text-foreground bg-input",
          "border-2",
          error ? "border-error-500" : "border-border",
          "focus:outline-none focus:border-primary-500",
          "transition-colors resize-y",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          className,
        )}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-1.5 text-sm text-error-600" role="alert">
          {error}
        </p>
      )}
      {helperText && !error && (
        <p id={helperId} className="mt-1.5 text-sm text-muted-foreground">
          {helperText}
        </p>
      )}
    </div>
  );
}
