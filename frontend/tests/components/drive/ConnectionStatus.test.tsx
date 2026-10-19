import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ConnectionStatus from "@/components/drive/ConnectionStatus";

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ token: "t" }) }));

describe("ConnectionStatus", () => {
  it("links to the privacy policy before Drive is connected", () => {
    render(<ConnectionStatus status={null} onStatusChange={vi.fn()} />);

    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});
