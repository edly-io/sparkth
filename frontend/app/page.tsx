import type { Metadata } from "next";
import HomeClient from "./page-client";

export const metadata: Metadata = {
  title: "Sparkth — AI-Powered Learning Platform",
  description:
    "Create engaging educational content with AI. Transform your resources into courses with ease.",
};

export default function Home() {
  return <HomeClient />;
}
