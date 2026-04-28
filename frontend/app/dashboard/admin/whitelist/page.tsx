import type { Metadata } from "next";
import WhitelistPage from "./WhitelistPage";

export const metadata: Metadata = {
  title: "Email Whitelist | Sparkth",
  description: "Manage whitelisted email addresses for registration",
};

export default function Page() {
  return <WhitelistPage />;
}
