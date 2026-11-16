"use client";

import { Suspense } from "react";
import ChatInterfaceWithParams from "@/plugins/compose/src/components/layout/ChatInterfaceWithParams";

export default function Compose() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          Loading…
        </div>
      }
    >
      <ChatInterfaceWithParams />
    </Suspense>
  );
}
