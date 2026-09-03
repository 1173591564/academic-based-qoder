import { describe, expect, it } from "vitest";

import {
  isNavigationItemVisible,
  type NavigationItem,
} from "./App";
import { tenantRouteFromPath } from "./pages/TenantsPage";

describe("capability-driven navigation", () => {
  const backendItem: NavigationItem = {
    label: "Backends",
    icon: "B",
    path: "/console/backends",
    capability: "backend:read",
  };

  it("shows public console pages without a capability hint", () => {
    expect(
      isNavigationItemVisible(
        { label: "Tenants", icon: "T", path: "/console/tenants" },
        [],
      ),
    ).toBe(true);
  });

  it("only shows privileged pages when the capability is advertised", () => {
    expect(isNavigationItemVisible(backendItem, [])).toBe(false);
    expect(isNavigationItemVisible(backendItem, ["backend:read"])).toBe(true);
  });
});

describe("tenantRouteFromPath", () => {
  it("parses tenant detail sections without accepting arbitrary suffixes", () => {
    expect(tenantRouteFromPath("/console/tenants/tenant-1/policies")).toEqual({
      tenantId: "tenant-1",
      section: "policies",
    });
    expect(tenantRouteFromPath("/console/tenants/tenant-1/unknown")).toEqual({
      tenantId: null,
      section: "summary",
    });
  });
});
