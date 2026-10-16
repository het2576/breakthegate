import { NextResponse, type NextRequest } from "next/server";

// Same-origin /api proxy (docs/PRD.md 5.3). next.config.ts rewrites /api/* to
// API_ORIGIN; this runs first and sets the two headers the API trusts. Anything
// a client sent under those names is dropped, so neither can be forged.
export const CLIENT_IP_HEADER = "x-btg-client-ip";
export const PROXY_SECRET_HEADER = "x-btg-proxy-secret";

export function clientIp(request: NextRequest): string | null {
  // On Vercel, x-real-ip is set by the platform. Locally neither header may
  // exist; the API then skips per-IP limits. Verify on the first deploy.
  const real = request.headers.get("x-real-ip")?.trim();
  if (real) return real;
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || null;
}

export function proxy(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.delete(CLIENT_IP_HEADER);
  headers.delete(PROXY_SECRET_HEADER);

  const ip = clientIp(request);
  if (ip) headers.set(CLIENT_IP_HEADER, ip);
  const secret = process.env.PROXY_SECRET;
  if (secret) headers.set(PROXY_SECRET_HEADER, secret);

  // request.headers (not headers) so the values go upstream, never to the client.
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: "/api/:path*",
};
