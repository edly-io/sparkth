import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithIntl } from "@/tests/intl-test-utils";

import { ApiRequestError } from "@/lib/api";

const search = vi.hoisted(() => ({ params: new URLSearchParams("token=abc") }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => search.params,
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, confirmPasswordReset: vi.fn() };
});

import { confirmPasswordReset } from "@/lib/api";
import ResetPasswordForm from "@/app/reset-password/ResetPasswordForm";

const NEW = "N3w-Password!";

beforeEach(() => {
  vi.clearAllMocks();
  search.params = new URLSearchParams("token=abc");
});

async function fill(next: string, confirm: string) {
  await userEvent.type(screen.getByLabelText("New password"), next);
  await userEvent.type(screen.getByLabelText("Confirm new password"), confirm);
  await userEvent.click(screen.getByRole("button", { name: "Reset password" }));
}

describe("ResetPasswordForm", () => {
  it("sets the new password with the link's token and offers sign in", async () => {
    vi.mocked(confirmPasswordReset).mockResolvedValue(undefined);
    renderWithIntl(<ResetPasswordForm />);

    await fill(NEW, NEW);

    expect(confirmPasswordReset).toHaveBeenCalledWith({ token: "abc", new_password: NEW });
    expect(await screen.findByRole("heading", { name: "Password reset" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to sign in" })).toHaveAttribute("href", "/login");
  });

  it("does not send the request when the passwords differ", async () => {
    renderWithIntl(<ResetPasswordForm />);

    await fill(NEW, "Different-1!");

    expect(confirmPasswordReset).not.toHaveBeenCalled();
    expect(screen.getByText("The new passwords don't match.")).toBeInTheDocument();
  });

  it("shows a weak password error against the new password field", async () => {
    vi.mocked(confirmPasswordReset).mockRejectedValue(
      new ApiRequestError(
        {
          message: "Validation error",
          fieldErrors: { new_password: "Password must be at least 8 characters" },
        },
        422,
      ),
    );
    renderWithIntl(<ResetPasswordForm />);

    await fill("short", "short");

    expect(await screen.findByText("Password must be at least 8 characters")).toBeInTheDocument();
    expect(screen.getByLabelText("New password")).toHaveValue("short");
  });

  it("shows why a refused link failed and offers a new one", async () => {
    vi.mocked(confirmPasswordReset).mockRejectedValue(
      new ApiRequestError(
        { message: "This password reset link has expired. Request a new one.", fieldErrors: {} },
        400,
      ),
    );
    renderWithIntl(<ResetPasswordForm />);

    await fill(NEW, NEW);

    expect(
      await screen.findByText("This password reset link has expired. Request a new one."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a new link" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
  });

  it("shows a generic error when the request fails to connect", async () => {
    vi.mocked(confirmPasswordReset).mockRejectedValue(new Error("offline"));
    renderWithIntl(<ResetPasswordForm />);

    await fill(NEW, NEW);

    expect(
      await screen.findByText("We couldn't reset your password. Please try again."),
    ).toBeInTheDocument();
  });

  it("explains a link with no token instead of showing the form", () => {
    search.params = new URLSearchParams();
    renderWithIntl(<ResetPasswordForm />);

    expect(screen.getByText("This password reset link is incomplete.")).toBeInTheDocument();
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a new link" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });
});
