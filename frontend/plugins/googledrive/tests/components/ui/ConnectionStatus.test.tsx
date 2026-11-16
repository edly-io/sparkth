import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ConnectionStatus from "@/plugins/googledrive/src/components/ui/ConnectionStatus";

vi.mock("@/lib/auth/hooks", () => ({ useAuth: () => ({ token: "t" }) }));

describe("ConnectionStatus", () => {
  it("links to the privacy policy before Drive is connected", () => {
    render(<ConnectionStatus status={null} onStatusChange={vi.fn()} />);

    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});
