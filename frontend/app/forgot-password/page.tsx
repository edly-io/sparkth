import type { Metadata } from "next";
import ForgotPasswordForm from "./ForgotPasswordForm";

export const metadata: Metadata = {
  title: "Forgot password | Sparkth",
  description: "Get a link to reset your Sparkth password",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
