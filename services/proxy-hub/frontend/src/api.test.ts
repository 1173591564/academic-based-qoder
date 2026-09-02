import { describe, expect, it } from "vitest";

import { getCookie } from "./api";

describe("getCookie", () => {
  it("returns an exact decoded cookie value", () => {
    expect(getCookie("other=1; proxy_hub_csrf=a%2Fb; final=2", "proxy_hub_csrf"))
      .toBe("a/b");
  });

  it("does not match a cookie name prefix", () => {
    expect(getCookie("proxy_hub_csrf_old=value", "proxy_hub_csrf")).toBeNull();
  });
});
