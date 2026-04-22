import type { Metadata } from "next";
import CallbackHandler from "./CallbackHandler";

export const metadata: Metadata = {
  title: "Signing in… | Sparkth",
  description: "Completing your sign-in to Sparkth",
};

export default function CallbackPage() {
  return <CallbackHandler />;
}
