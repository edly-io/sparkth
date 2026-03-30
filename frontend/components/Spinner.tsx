import { Loader2 } from "lucide-react";

const sizeClasses = {
  sm: "w-4 h-4",
  md: "h-6 w-6",
  lg: "h-10 w-10",
} as const;

interface SpinnerProps {
  size?: keyof typeof sizeClasses;
  className?: string;
}

export function Spinner({ size = "lg", className = "" }: SpinnerProps) {
  return <Loader2 className={`${sizeClasses[size]} animate-spin text-primary-500 ${className}`} />;
}
