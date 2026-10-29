"use client";

import { Suspense } from "react";
import ChatInterfaceWithParams from "./components/ChatInterfaceWithParams";

export default function ChatInterface() {
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
