import type { ReactNode } from "react";
import Link from "next/link";

import { SparkthLogo } from "@/components/SparkthLogo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Card } from "@/components/ui/Card";

/** The centred, logo-topped card the signed-out pages (password reset and friends) render in. */
export function AuthCard({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh flex items-center justify-center bg-background py-6 px-4 sm:py-12 sm:px-6 lg:px-8 transition-colors">
      <Card variant="elevated" className="max-w-md w-full p-4 sm:p-6 relative">
        <div className="absolute top-3 right-3 sm:top-4 sm:right-4">
          <ThemeToggle />
        </div>
        <div className="flex justify-center mb-1">
          <SparkthLogo size={56} />
        </div>
        <div className="space-y-4 py-2">{children}</div>
      </Card>
    </div>
  );
}

/** A signed-out page's centred heading and the line of text under it. */
export function AuthHeading({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <div className="text-center space-y-2">
      <h2 className="text-2xl sm:text-3xl font-bold text-foreground">{title}</h2>
      {subtitle && <p className="text-sm sm:text-base text-muted-foreground">{subtitle}</p>}
    </div>
  );
}

/** The primary-coloured text link the signed-out pages use to move between each other. */
export function AuthLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <p className="text-center text-sm">
      <Link
        href={href}
        className="font-medium text-primary-500 hover:text-primary-700 transition-colors"
      >
        {children}
      </Link>
    </p>
  );
}
