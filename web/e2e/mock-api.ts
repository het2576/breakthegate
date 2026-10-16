import type { Page, Request, Route } from "@playwright/test";

import levels from "./fixtures/levels.json" with { type: "json" };

export interface AttemptCall {
  body: Record<string, unknown>;
  key: string | null;
}

type Responder = (call: AttemptCall, index: number) => { status: number; body: unknown; headers?: Record<string, string> };

export function result(overrides: Record<string, unknown> = {}) {
  return {
    attempt_id: `a-${Math.random().toString(36).slice(2, 10)}`,
    approved: false,
    p_safe: 0.31,
    threshold: 0.5,
    deciding_layer: "model_a",
    layers: [{ name: "model_a", passed: false, p_safe: 0.31, detail: "Probability safe 0.31, needs 0.50" }],
    verified: true,
    points: 0,
    reveal_id: null,
    gate_version: "2026-10-16.1",
    ...overrides,
  };
}

export const approved = (overrides: Record<string, unknown> = {}) =>
  result({
    approved: true,
    p_safe: 0.93,
    layers: [{ name: "model_a", passed: true, p_safe: 0.93, detail: "Probability safe 0.93" }],
    points: 147,
    ...overrides,
  });

export function apiError(status: number, code: string, message: string, retryAfter?: number) {
  return {
    status,
    body: { error: { code, message, ...(retryAfter ? { retry_after: retryAfter } : {}) } },
    headers: retryAfter ? { "retry-after": String(retryAfter) } : undefined,
  };
}

/**
 * Mock the game API in the browser. Starts with no session (the consent sheet
 * shows); POST /api/sessions creates one. Attempts answer via `onAttempt`.
 */
export async function mockApi(page: Page, onAttempt: Responder, opts: { session?: boolean } = {}) {
  let hasSession = opts.session ?? false;
  let session = { handle: null as string | null, consent_training: false, created_at: "2026-10-16T00:00:00Z" };
  const attempts: AttemptCall[] = [];
  const sessionBodies: unknown[] = [];

  const json = (route: Route, status: number, body: unknown, headers?: Record<string, string>) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body), headers });

  await page.route("**/api/**", async (route: Route, request: Request) => {
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/levels") return json(route, 200, levels);
    if (path === "/api/sessions/me" && method === "GET") {
      return hasSession
        ? json(route, 200, { session })
        : json(route, 401, { error: { code: "no_session", message: "Start a session first." } });
    }
    if (path === "/api/sessions" && method === "POST") {
      sessionBodies.push(request.postDataJSON());
      hasSession = true;
      const consent = (request.postDataJSON() as { consent_training: boolean }).consent_training;
      session = { ...session, consent_training: consent };
      return json(route, 201, { session });
    }
    if (path === "/api/sessions/me" && method === "PATCH") {
      const patch = request.postDataJSON() as Partial<typeof session>;
      session = { ...session, ...patch };
      return json(route, 200, { session });
    }
    if (path === "/api/sessions/me/delete" && method === "POST") {
      hasSession = false;
      return json(route, 200, { deleted: true });
    }
    if (path === "/api/leaderboard") {
      return json(route, 200, { level: Number(url.searchParams.get("level")), entries: [{ rank: 1, handle: "gatecrasher", score: 147, attempts: 1 }] });
    }
    if (path === "/api/attempts/me") return json(route, 200, { attempts: [], next_before: null });
    if (path === "/api/attempts" && method === "POST") {
      const call = { body: request.postDataJSON() as Record<string, unknown>, key: request.headers()["idempotency-key"] ?? null };
      attempts.push(call);
      const r = onAttempt(call, attempts.length - 1);
      return json(route, r.status, r.body, r.headers);
    }
    if (path.startsWith("/api/reveals/") && path.endsWith("/claim") && method === "POST") {
      return json(route, 200, {
        variant: "standard",
        level: 1,
        attempts: 1,
        seconds: 12,
        badge: "Gate breaker, level 1",
        video_id: null,
      });
    }
    return json(route, 404, { error: { code: "not_found", message: "Not found." } });
  });

  return { attempts, sessionBodies };
}

/** Start a session through the consent sheet, then fill the form. */
export async function startAndFill(page: Page, task = "Tidy up old config", command = "rm -rf /etc") {
  await page.getByTestId("consent-start").click();
  await page.getByTestId("consent-sheet").waitFor({ state: "detached" });
  await page.getByTestId("task").fill(task);
  await page.getByTestId("command").fill(command);
}
