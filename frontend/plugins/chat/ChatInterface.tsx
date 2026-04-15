"use client";

import { Suspense } from "react";
import ChatInterfaceInner from "./components/ChatInterfaceInner";

export default function ChatInterface() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          Loading…
        </div>
      }
    >
      <ChatInterfaceInner />
    </Suspense>
  );
}
