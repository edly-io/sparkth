"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";

interface HeaderProps {
  isAuthenticated: boolean;
  logout: () => void;
}

export default function SparkthHeader({
  isAuthenticated,
  logout,
}: HeaderProps) {
  return (
    <nav className="bg-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <span className="text-xl font-bold text-gray-900">Sparkth</span>
          </div>
          <div className="flex items-center space-x-4">
            {isAuthenticated ? (
              <Button
                variant="error"
                size="sm"
                onClick={logout}
              >
                Logout
              </Button>
            ) : (
              <>
                <Link
                  href="/login"
                  className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
