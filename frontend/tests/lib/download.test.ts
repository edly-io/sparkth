import { describe, it, expect, vi, afterEach } from "vitest";

import { downloadBlob } from "@/lib/download";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("downloadBlob", () => {
  it("clicks a temporary link to the blob named after the file, then cleans up", () => {
    const blob = new Blob(["a,b"]);
    const createObjectURL = vi.fn().mockReturnValue("blob:1");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    const clicked: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      function (this: HTMLAnchorElement) {
        clicked.push(this);
      },
    );

    downloadBlob(blob, "report.csv");

    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(clicked).toHaveLength(1);
    expect(clicked[0].download).toBe("report.csv");
    expect(clicked[0].getAttribute("href")).toBe("blob:1");
    expect(document.querySelector("a[download]")).toBeNull();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:1");
    vi.unstubAllGlobals();
  });
});
