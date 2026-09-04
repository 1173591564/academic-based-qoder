import { describe, expect, it, vi } from "vitest";

import { copyText, type CopyEnvironment } from "./clipboard";

describe("copyText", () => {
  it("uses the Clipboard API when available", async () => {
    const environment: CopyEnvironment = {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
      fallbackCopy: vi.fn(),
    };

    await copyText("scholar-token", environment);

    expect(environment.clipboard?.writeText).toHaveBeenCalledWith("scholar-token");
    expect(environment.fallbackCopy).not.toHaveBeenCalled();
  });

  it("falls back when the Clipboard API is unavailable", async () => {
    const environment: CopyEnvironment = {
      fallbackCopy: vi.fn().mockReturnValue(true),
    };

    await copyText("scholar-token", environment);

    expect(environment.fallbackCopy).toHaveBeenCalledWith("scholar-token");
  });

  it("falls back when the Clipboard API rejects", async () => {
    const environment: CopyEnvironment = {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error("not allowed")) },
      fallbackCopy: vi.fn().mockReturnValue(true),
    };

    await copyText("scholar-token", environment);

    expect(environment.fallbackCopy).toHaveBeenCalledWith("scholar-token");
  });

  it("rejects when neither copy mechanism succeeds", async () => {
    const environment: CopyEnvironment = {
      fallbackCopy: vi.fn().mockReturnValue(false),
    };

    await expect(copyText("scholar-token", environment)).rejects.toThrow(
      "Clipboard write failed",
    );
  });
});
