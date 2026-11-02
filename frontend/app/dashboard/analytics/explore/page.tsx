import type { Metadata } from "next";
import ExplorePage from "./ExplorePage";

export const metadata: Metadata = {
  title: "Explore · Analytics | Sparkth",
  description: "Charts built from recorded events",
};

export default function Page() {
  return <ExplorePage />;
}
