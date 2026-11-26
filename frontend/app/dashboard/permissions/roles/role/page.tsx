import { Suspense } from "react";
import type { Metadata } from "next";
import { Spinner } from "@/core/components/ui/Spinner";
import RolePage from "./RolePage";

export const metadata: Metadata = {
  title: "Role · Access & permissions | Sparkth",
  description: "What one role allows",
};

export default function Page() {
  // The role comes from the query string, which a static export only reads under Suspense; the
  // spinner matches the page's own while the role loads, so loading shows as one.
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      }
    >
      <RolePage />
    </Suspense>
  );
}
