import type { Metadata } from "next";
import AuthoringPage from "./AuthoringPage";

export const metadata: Metadata = {
  title: "Course authoring · Analytics | Sparkth",
  description: "Instructor course-authoring activity",
};

export default function Page() {
  return <AuthoringPage />;
}
