"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { SparkthLogo } from "./SparkthLogo";

interface HeaderProps {
  isAuthenticated: boolean;
  logout: () => void;
}

export default function SparkthHeader({
  isAuthenticated,
  logout,
}: HeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav className="bg-card border-b border-border shadow-sm transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link href="/">
              <SparkthLogo size={40} />
            </Link>
          </div>

          {/* Desktop navigation */}
          <div className="hidden sm:flex items-center space-x-4">
            {isAuthenticated ? (
              <Button
                variant="error"
                size="sm"
                onClick={logout}
                className="min-h-[44px]"
              >
                Logout
              </Button>
            ) : (
              <>
                <Link
                  href="/login"
                  className="inline-flex items-center px-4 py-2 min-h-[44px] border border-border text-sm font-medium rounded-md text-foreground bg-card hover:bg-surface-variant focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center px-4 py-2 min-h-[44px] border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                >
                  Register
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex items-center gap-2 sm:hidden">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            >
              {mobileMenuOpen ? (
                <X className="h-6 w-6" />
              ) : (
                <Menu className="h-6 w-6" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Mobile menu dropdown */}
      {mobileMenuOpen && (
        <div className="sm:hidden border-t border-border bg-card">
          <div className="px-4 py-3 space-y-3">
            {isAuthenticated ? (
              <Button
                variant="error"
                fullWidth
                onClick={() => {
                  logout();
                  setMobileMenuOpen(false);
                }}
                className="min-h-[44px]"
              >
                Logout
              </Button>
            ) : (
              <>
                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center justify-center w-full px-4 py-3 min-h-[44px] border border-border text-base font-medium rounded-md text-foreground bg-card hover:bg-surface-variant focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center justify-center w-full px-4 py-3 min-h-[44px] border border-transparent text-base font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
