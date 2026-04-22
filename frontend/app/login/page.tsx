import type { Metadata } from "next";
import LoginForm from "./LoginForm";

export const metadata: Metadata = {
  title: "Log in | Sparkth",
  description: "Sign in to your Sparkth account",
};

export default function LoginPage() {
  return <LoginForm />;
}
