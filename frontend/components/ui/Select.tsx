"use client";

import { forwardRef, useId, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  helperText?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ id, label, error, helperText, options, placeholder, className, ...props }, ref) => {
    const generatedId = useId();
    const selectId = id || props.name || generatedId;

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={selectId} className="block text-sm font-medium text-foreground mb-1.5">
            {label}
            {props.required && (
              <span aria-hidden="true" className="ml-0.5 text-error-500">
                *
              </span>
            )}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            {...props}
            aria-describedby={error ? `${selectId}-error` : undefined}
            aria-invalid={error ? true : undefined}
            className={cn(
              "appearance-none block w-full px-4 py-3 pr-10 rounded-lg",
              "text-foreground bg-input",
              "border-2",
              error ? "border-error-500" : "border-border",
              "focus:outline-none focus:border-primary-500",
              "transition-colors",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              className,
            )}
          >
            {placeholder && (
              <option value="" hidden>
                {placeholder}
              </option>
            )}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            size={16}
            aria-hidden="true"
          />
        </div>
        {error && (
          <p id={`${selectId}-error`} className="mt-1.5 text-sm text-error-600">
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="mt-1.5 text-sm text-muted-foreground">{helperText}</p>
        )}
      </div>
    );
  },
);

Select.displayName = "Select";
