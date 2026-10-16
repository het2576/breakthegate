// Typed client for the game API. Only relative /api/* URLs: the Next.js proxy
// forwards them to the API (PRD 5.3), so the session cookie stays first party.

import type {
  AttemptDraft,
  AttemptResult,
  ErrorCode,
  HistoryResponse,
  LeaderboardResponse,
  LevelsResponse,
  RevealClaim,
  Session,
} from "./types";

const KNOWN_CODES = new Set<ErrorCode>([
  "forbidden",
  "no_session",
  "validation",
  "moderation",
  "level_locked",
  "idempotency_key_reused",
  "idempotency_in_progress",
  "already_claimed",
  "reveal_expired",
  "rate_limited",
  "warming_up",
  "verifier_unavailable",
  "gate_unavailable",
  "breaker_open",
  "paused",
  "not_found",
]);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: ErrorCode,
    message: string,
    readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; retry_after?: number };
}

export async function parseError(res: Response): Promise<ApiError> {
  let body: ErrorBody = {};
  try {
    body = (await res.json()) as ErrorBody;
  } catch {
    // Not JSON (a proxy or platform error page): fall through to defaults.
  }
  const raw = body.error?.code ?? "";
  const code: ErrorCode = KNOWN_CODES.has(raw as ErrorCode) ? (raw as ErrorCode) : "unknown";
  const header = Number(res.headers.get("retry-after"));
  const retryAfter = body.error?.retry_after ?? (Number.isFinite(header) && header > 0 ? header : null);
  return new ApiError(res.status, code, body.error?.message ?? `Request failed (${res.status}).`, retryAfter);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      credentials: "same-origin",
      headers: { "content-type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network", "Could not reach the gate.");
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

export const api = {
  levels: () => request<LevelsResponse>("/api/levels"),
  me: async (): Promise<Session | null> => {
    try {
      return (await request<{ session: Session }>("/api/sessions/me")).session;
    } catch (err) {
      if (err instanceof ApiError && err.code === "no_session") return null;
      throw err;
    }
  },
  startSession: (consentTraining: boolean, turnstileToken?: string | null) =>
    request<{ session: Session }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        consent_training: consentTraining,
        ...(turnstileToken ? { turnstile_token: turnstileToken } : {}),
      }),
    }).then((r) => r.session),
  updateSession: (changes: { handle?: string | null; consent_training?: boolean }) =>
    request<{ session: Session }>("/api/sessions/me", {
      method: "PATCH",
      body: JSON.stringify(changes),
    }).then((r) => r.session),
  deleteSession: () => request<{ deleted: boolean }>("/api/sessions/me/delete", { method: "POST" }),
  leaderboard: (level: number) => request<LeaderboardResponse>(`/api/leaderboard?level=${level}`),
  history: (level: number, limit = 50) =>
    request<HistoryResponse>(`/api/attempts/me?level=${level}&limit=${limit}`),
  attempt: (draft: AttemptDraft, idempotencyKey: string) =>
    request<AttemptResult>("/api/attempts", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(draft),
    }),
  claimReveal: (revealId: string) =>
    request<RevealClaim>(`/api/reveals/${encodeURIComponent(revealId)}/claim`, { method: "POST" }),
};

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
