import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithIntl } from "../../../intl-test-utils";

import { ApiRequestError, type CurrentUser } from "@/lib/api";

const auth = vi.hoisted(() => ({
  user: null as CurrentUser | null,
  refreshUser: vi.fn(),
}));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token", user: auth.user, refreshUser: auth.refreshUser }),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, updateCurrentUser: vi.fn(), changePassword: vi.fn() };
});

import { changePassword, updateCurrentUser } from "@/lib/api";
import ProfilePage from "@/app/dashboard/profile/ProfilePage";

const passwordUser: CurrentUser = {
  id: 1,
  name: "Ada Lovelace",
  username: "ada",
  email: "ada@example.com",
  email_verified: true,
  has_password: true,
  is_admin: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = passwordUser;
  auth.refreshUser.mockResolvedValue(undefined);
});

describe("ProfilePage account details", () => {
  it("shows the username, email, verification status and sign-in method", () => {
    renderWithIntl(<ProfilePage />);

    expect(screen.getByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByText("ada")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("Email and password")).toBeInTheDocument();
  });

  it("shows an unverified email and Google sign-in for an account with no password", () => {
    auth.user = { ...passwordUser, email_verified: false, has_password: false };

    renderWithIntl(<ProfilePage />);

    expect(screen.getByText("Not verified")).toBeInTheDocument();
    expect(screen.getByText("Google")).toBeInTheDocument();
  });

  it("shows a spinner until the user has loaded", () => {
    auth.user = null;

    renderWithIntl(<ProfilePage />);

    expect(screen.getByText("Loading your profile…")).toBeInTheDocument();
  });
});

describe("ProfilePage name form", () => {
  it("saves the trimmed name and refreshes the signed-in user", async () => {
    vi.mocked(updateCurrentUser).mockResolvedValue({ ...passwordUser, name: "Ada King" });
    renderWithIntl(<ProfilePage />);

    const input = screen.getByLabelText("Name");
    await userEvent.clear(input);
    await userEvent.type(input, "  Ada King  ");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(updateCurrentUser).toHaveBeenCalledWith("test-token", { name: "Ada King" });
    expect(await screen.findByText("Your name has been updated.")).toBeInTheDocument();
    expect(auth.refreshUser).toHaveBeenCalled();
  });

  it("disables Save while the name is unchanged or blank", async () => {
    renderWithIntl(<ProfilePage />);

    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();

    await userEvent.clear(screen.getByLabelText("Name"));
    await userEvent.type(screen.getByLabelText("Name"), "   ");
    expect(save).toBeDisabled();
  });

  it("caps the name at 30 characters", () => {
    renderWithIntl(<ProfilePage />);

    expect(screen.getByLabelText("Name")).toHaveAttribute("maxLength", "30");
  });

  it("shows the server's error for a rejected name", async () => {
    vi.mocked(updateCurrentUser).mockRejectedValue(
      new ApiRequestError({ message: "Bad", fieldErrors: { name: "Name is too long" } }, 422),
    );
    renderWithIntl(<ProfilePage />);

    await userEvent.type(screen.getByLabelText("Name"), "!");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Name is too long")).toBeInTheDocument();
    expect(auth.refreshUser).not.toHaveBeenCalled();
  });
});

describe("ProfilePage password form", () => {
  async function fillPasswords(current: string, next: string, confirm: string) {
    await userEvent.type(screen.getByLabelText("Current password"), current);
    await userEvent.type(screen.getByLabelText("New password"), next);
    await userEvent.type(screen.getByLabelText("Confirm new password"), confirm);
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));
  }

  it("changes the password and clears the form", async () => {
    vi.mocked(changePassword).mockResolvedValue(undefined);
    renderWithIntl(<ProfilePage />);

    await fillPasswords("Old-Pass1!", "N3w-Password!", "N3w-Password!");

    expect(changePassword).toHaveBeenCalledWith("test-token", {
      current_password: "Old-Pass1!",
      new_password: "N3w-Password!",
    });
    expect(await screen.findByText("Your password has been changed.")).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toHaveValue("");
    expect(screen.getByLabelText("New password")).toHaveValue("");
    expect(screen.getByLabelText("Confirm new password")).toHaveValue("");
  });

  it("does not send the request when the new passwords differ", async () => {
    renderWithIntl(<ProfilePage />);

    await fillPasswords("Old-Pass1!", "N3w-Password!", "N3w-Password?");

    expect(screen.getByText("The new passwords don't match.")).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("shows a wrong current password against that field", async () => {
    vi.mocked(changePassword).mockRejectedValue(
      new ApiRequestError({ message: "Your current password is incorrect.", fieldErrors: {} }, 400),
    );
    renderWithIntl(<ProfilePage />);

    await fillPasswords("wrong", "N3w-Password!", "N3w-Password!");

    expect(await screen.findByText("Your current password is incorrect.")).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toHaveValue("wrong");
  });

  it("shows a weak new password error against the new password field", async () => {
    vi.mocked(changePassword).mockRejectedValue(
      new ApiRequestError(
        { message: "Bad", fieldErrors: { new_password: "Password must be at least 8 characters" } },
        422,
      ),
    );
    renderWithIntl(<ProfilePage />);

    await fillPasswords("Old-Pass1!", "weak", "weak");

    expect(await screen.findByText("Password must be at least 8 characters")).toBeInTheDocument();
  });

  it("is replaced by a note for an account that signs in with Google only", () => {
    auth.user = { ...passwordUser, has_password: false };

    renderWithIntl(<ProfilePage />);

    expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
    expect(
      screen.getByText("You sign in with Google, so there is no Sparkth password to change."),
    ).toBeInTheDocument();
  });
});

describe("ProfilePage submit errors", () => {
  it("falls back to a generic message when the name save fails to connect", async () => {
    vi.mocked(updateCurrentUser).mockRejectedValue(new TypeError("boom"));
    renderWithIntl(<ProfilePage />);

    await userEvent.type(screen.getByLabelText("Name"), "!");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(
        screen.getByText("We couldn't update your name. Please try again."),
      ).toBeInTheDocument(),
    );
  });
});
