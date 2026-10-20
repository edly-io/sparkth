import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithIntl } from "../../intl-test-utils";

import { ApiRequestError } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, requestPasswordReset: vi.fn() };
});

import { requestPasswordReset } from "@/lib/api";
import ForgotPasswordForm from "@/app/forgot-password/ForgotPasswordForm";

beforeEach(() => {
  vi.clearAllMocks();
});

async function submit(email: string) {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));
}

describe("ForgotPasswordForm", () => {
  it("sends the trimmed email and tells the user to check their inbox", async () => {
    vi.mocked(requestPasswordReset).mockResolvedValue(undefined);
    renderWithIntl(<ForgotPasswordForm />);

    await submit("  ada@example.com ");

    expect(requestPasswordReset).toHaveBeenCalledWith("ada@example.com");
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByText(/ada@example.com/)).toBeInTheDocument();
  });

  it("disables the button until an email is entered", () => {
    renderWithIntl(<ForgotPasswordForm />);

    expect(screen.getByRole("button", { name: "Send reset link" })).toBeDisabled();
  });

  it("asks the user to wait when the request is rate limited", async () => {
    vi.mocked(requestPasswordReset).mockRejectedValue(
      new ApiRequestError({ message: "rate_limited", fieldErrors: {} }, 429),
    );
    renderWithIntl(<ForgotPasswordForm />);

    await submit("ada@example.com");

    expect(
      await screen.findByText(
        "A reset link was just sent. Please wait a minute before asking again.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a generic error when the request fails", async () => {
    vi.mocked(requestPasswordReset).mockRejectedValue(new Error("offline"));
    renderWithIntl(<ForgotPasswordForm />);

    await submit("ada@example.com");

    expect(
      await screen.findByText("We couldn't send the reset link. Please try again."),
    ).toBeInTheDocument();
  });

  it("links back to sign in", () => {
    renderWithIntl(<ForgotPasswordForm />);

    expect(screen.getByRole("link", { name: "Back to sign in" })).toHaveAttribute("href", "/login");
  });
});
