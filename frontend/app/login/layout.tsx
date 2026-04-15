import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Log in | Sparkth",
  description: "Sign in to your Sparkth account",
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
