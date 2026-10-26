import { use } from "react";
import { AuthContext, type AuthContextType } from "@/core/auth/context";

export function useAuth(): AuthContextType {
  const context = use(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
