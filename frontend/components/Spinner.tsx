import { Loader2 } from "lucide-react";

const sizeClasses = {
  sm: "size-4",
  md: "size-6",
  lg: "size-10",
} as const;

interface SpinnerProps {
  size?: keyof typeof sizeClasses;
  className?: string;
}

export function Spinner({ size = "lg", className = "" }: SpinnerProps) {
  return <Loader2 className={`${sizeClasses[size]} animate-spin text-primary-500 ${className}`} />;
}
