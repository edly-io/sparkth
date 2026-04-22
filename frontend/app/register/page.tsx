import type { Metadata } from "next";
import RegisterForm from "./RegisterForm";

export const metadata: Metadata = {
  title: "Create account | Sparkth",
  description: "Create a new Sparkth account",
};

export default function RegisterPage() {
  return <RegisterForm />;
}
