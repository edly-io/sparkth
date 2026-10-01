import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import PrivacyPolicy from "@/app/privacy/page";

describe("PrivacyPolicy", () => {
  it("states the Google API Limited Use commitment verbatim", () => {
    render(<PrivacyPolicy />);

    expect(
      screen.getByText(
        "Sparkth's use and transfer of information received from Google APIs will adhere to the Google API Services User Data Policy, including the Limited Use requirements.",
      ),
    ).toBeInTheDocument();
  });

  it("states that Google Workspace data is not used to train AI models", () => {
    render(<PrivacyPolicy />);

    expect(
      screen.getByText(
        "Sparkth does not use Google Workspace data to develop, improve, or train generalized AI or machine learning models.",
      ),
    ).toBeInTheDocument();
  });
});
