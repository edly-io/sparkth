import { InputHTMLAttributes, forwardRef } from "react";
import { twMerge } from "tailwind-merge";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  /**
   * Asks the browser and password managers not to fill the input, overriding any `autoComplete`
   * passed with it. Set it on a field that holds a third-party credential, which a saved login
   * for this site must never fill.
   */
  noAutofill?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, helperText, id, type, noAutofill, ...props }, ref) => {
    const inputId = id || props.name;
    const errorId = error && inputId ? `${inputId}-error` : undefined;

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-foreground mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          type={type}
          className={twMerge(
            "appearance-none block w-full px-4 py-3 rounded-lg",
            "placeholder-muted text-foreground",
            "bg-input",
            "border-2",
            "focus:outline-none focus:border-primary-500",
            "transition-colors",
            error ? "border-error-500" : "border-border",
            className,
          )}
          aria-invalid={error ? true : undefined}
          aria-describedby={errorId}
          {...props}
          // Chrome ignores "off" on a password field, so a password opts out as "new-password".
          {...(noAutofill && {
            autoComplete: type === "password" ? "new-password" : "off",
            "data-1p-ignore": true,
            "data-lpignore": "true",
            "data-bwignore": true,
          })}
        />
        {error && (
          <p id={errorId} role="alert" className="mt-1.5 text-sm text-error-600">
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

Input.displayName = "Input";
