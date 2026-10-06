import type { Metadata } from "next";
import LoginsPage from "./LoginsPage";

export const metadata: Metadata = {
  title: "Logins · Analytics | Sparkth",
  description: "Login activity",
};

export default function Page() {
  return <LoginsPage />;
}
