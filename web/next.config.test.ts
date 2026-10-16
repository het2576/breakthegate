import { afterEach, describe, expect, it, vi } from "vitest";

async function loadRewrites() {
  vi.resetModules();
  const { default: config } = await import("./next.config");
  const rewrites = await config.rewrites!();
  if (!Array.isArray(rewrites)) throw new Error("expected a flat rewrites array");
  return rewrites;
}

describe("same-origin /api proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("rewrites /api/* to API_ORIGIN", async () => {
    vi.stubEnv("API_ORIGIN", "https://api.example.test");
    expect(await loadRewrites()).toEqual([
      { source: "/api/:path*", destination: "https://api.example.test/api/:path*" },
    ]);
  });

  it("falls back to the local API in dev", async () => {
    vi.stubEnv("API_ORIGIN", undefined);
    const [rule] = await loadRewrites();
    expect(rule.destination).toBe("http://127.0.0.1:8000/api/:path*");
  });
});
