import type { Metadata } from "next";
import ProfilePage from "./ProfilePage";

export const metadata: Metadata = {
  title: "Profile | Sparkth",
  description: "Your account details, name and password",
};

export default function Page() {
  return <ProfilePage />;
}
