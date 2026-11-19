import { describe, it, expect } from "vitest";

import { ApiRequestError, isNotFoundError } from "@/lib/api/errors";

const apiError = (status?: number) =>
  new ApiRequestError({ message: "x", fieldErrors: {} }, status);

describe("isNotFoundError", () => {
  it.each([404, 422])("treats an API answer of %i as a missing item", (status) => {
    expect(isNotFoundError(apiError(status))).toBe(true);
  });

  it.each([403, 500, undefined])(
    "does not treat an API answer of %s as a missing item",
    (status) => {
      expect(isNotFoundError(apiError(status))).toBe(false);
    },
  );

  it("does not treat a failure that never reached the API as a missing item", () => {
    expect(isNotFoundError(new Error("Network error: Failed to fetch"))).toBe(false);
  });
});
