import { describe, expect, it } from "vitest";

import { isActive, NAVIGATION } from "./App";

describe("single-lab navigation", () => {
  it("contains only Token management, service status, and audit log", () => {
    expect(NAVIGATION.map((item) => item.label)).toEqual([
      "Token management",
      "Service status",
      "Audit log",
    ]);
  });

  it("routes the console root exclusively to Token management", () => {
    expect(isActive("/console/", "/console/")).toBe(true);
    expect(isActive("/console/status", "/console/")).toBe(false);
    expect(isActive("/console/status", "/console/status")).toBe(true);
  });
});
