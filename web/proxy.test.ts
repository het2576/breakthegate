import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, proxy } from "./proxy";

// NextResponse.next({ request: { headers } }) forwards upstream request headers
// as x-middleware-request-<name> on the response object Next reads internally.
function upstream(res: Response, name: string): string | null {
  return res.headers.get(`x-middleware-request-${name}`);
}

function request(headers: Record<string, string>): NextRequest {
  return new NextRequest("http://localhost:3000/api/attempts", { headers });
}

describe("/api proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("only runs on /api", () => {
    expect(config.matcher).toBe("/api/:path*");
  });

  it("adds the proxy secret and the platform client IP", () => {
    vi.stubEnv("PROXY_SECRET", "s3cret");
    const res = proxy(request({ "x-real-ip": "203.0.113.7" }));
    expect(upstream(res, "x-btg-proxy-secret")).toBe("s3cret");
    expect(upstream(res, "x-btg-client-ip")).toBe("203.0.113.7");
  });

  it("drops forged trust headers from the client", () => {
    vi.stubEnv("PROXY_SECRET", "s3cret");
    const res = proxy(
      request({
        "x-btg-proxy-secret": "forged",
        "x-btg-client-ip": "6.6.6.6",
        "x-real-ip": "203.0.113.7",
      }),
    );
    expect(upstream(res, "x-btg-proxy-secret")).toBe("s3cret");
    expect(upstream(res, "x-btg-client-ip")).toBe("203.0.113.7");
  });

  it("never exposes the secret on the client response", () => {
    vi.stubEnv("PROXY_SECRET", "s3cret");
    const res = proxy(request({}));
    expect(res.headers.get("x-btg-proxy-secret")).toBeNull();
  });

  it("sends no client IP when the platform gives none", () => {
    vi.stubEnv("PROXY_SECRET", "s3cret");
    const res = proxy(request({ "x-btg-client-ip": "6.6.6.6" }));
    expect(upstream(res, "x-btg-client-ip")).toBeNull();
  });
});
