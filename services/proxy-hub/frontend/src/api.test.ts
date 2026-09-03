import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getCookie, mutationHeaders, request } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getCookie", () => {
  it("returns an exact decoded cookie value", () => {
    expect(getCookie("other=1; proxy_hub_csrf=a%2Fb; final=2", "proxy_hub_csrf"))
      .toBe("a/b");
  });

  it("does not match a cookie name prefix", () => {
    expect(getCookie("proxy_hub_csrf_old=value", "proxy_hub_csrf")).toBeNull();
  });
});

describe("mutationHeaders", () => {
  it("combines CSRF, content type, ETag, and idempotency metadata", () => {
    expect(
      mutationHeaders("proxy_hub_csrf=a%2Fb", {
        "If-Match": '"tenant:1:2"',
        "Idempotency-Key": "request-1",
      }),
    ).toEqual({
      "Content-Type": "application/json",
      "X-CSRF-Token": "a/b",
      "If-Match": '"tenant:1:2"',
      "Idempotency-Key": "request-1",
    });
  });

  it("fails closed without the CSRF cookie", () => {
    expect(() => mutationHeaders("other=value")).toThrowError(ApiError);
  });
});

describe("request", () => {
  it("returns an empty 204 response without parsing JSON", async () => {
    const json = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        headers: new Headers({ ETag: '"membership:1:2"' }),
        json,
      }),
    );

    await expect(request<void>("/resource", { method: "DELETE" })).resolves.toEqual({
      data: undefined,
      etag: '"membership:1:2"',
    });
    expect(json).not.toHaveBeenCalled();
  });

  it("uses same-origin credentials for browser session requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { ETag: '"resource:1"' },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await request<{ status: string }>("/resource");

    expect(fetchMock).toHaveBeenCalledWith(
      "/resource",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });
});
