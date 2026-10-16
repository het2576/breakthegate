// The attempt state machine (docs/ARCHITECTURE.md 3.6). Pure: the Game
// component performs the side effects (fetch, timers) and feeds events in.

import type { ApiError } from "./api";
import type { AttemptDraft, AttemptResult, ErrorCode } from "./types";

export type WaitReason = "warming_up" | "verifier_unavailable" | "in_progress";

export type Phase =
  | { kind: "idle" }
  | { kind: "submitting"; draft: AttemptDraft; key: string }
  | { kind: "warming"; reason: WaitReason; retryAt: number; draft: AttemptDraft; key: string }
  | { kind: "result"; result: AttemptResult }
  | { kind: "rate_limited"; until: number }
  | { kind: "resting"; until: number }
  | { kind: "paused" }
  | { kind: "error"; code: ErrorCode; message: string; field: "task" | "command" | null };

export type Event =
  | { type: "submit"; draft: AttemptDraft; key: string }
  | { type: "success"; result: AttemptResult }
  | { type: "failure"; error: ApiError; now: number }
  | { type: "retry" }
  | { type: "clear" };

export const DEFAULT_WAIT_S = 10;

const RETRY_WITH_SAME_KEY: Partial<Record<ErrorCode, WaitReason>> = {
  warming_up: "warming_up",
  verifier_unavailable: "verifier_unavailable",
  idempotency_in_progress: "in_progress",
};

export function reduce(phase: Phase, event: Event): Phase {
  switch (event.type) {
    case "submit":
      // Never two requests at once, and never auto-submit from a result.
      if (phase.kind === "submitting" || phase.kind === "warming") return phase;
      return { kind: "submitting", draft: event.draft, key: event.key };

    case "success":
      return phase.kind === "submitting" ? { kind: "result", result: event.result } : phase;

    case "failure": {
      if (phase.kind !== "submitting") return phase;
      return fromError(event.error, event.now, phase.draft, phase.key);
    }

    case "retry":
      return phase.kind === "warming"
        ? { kind: "submitting", draft: phase.draft, key: phase.key }
        : phase;

    case "clear":
      return phase.kind === "submitting" ? phase : { kind: "idle" };
  }
}

function fromError(error: ApiError, now: number, draft: AttemptDraft, key: string): Phase {
  const wait = (error.retryAfter ?? DEFAULT_WAIT_S) * 1000;
  const reason = RETRY_WITH_SAME_KEY[error.code];
  if (reason) {
    // Same draft, same Idempotency-Key: the server answers once (PRD 6.6).
    return { kind: "warming", reason, retryAt: now + (reason === "in_progress" ? 1000 : wait), draft, key };
  }
  switch (error.code) {
    case "rate_limited":
      return { kind: "rate_limited", until: now + wait };
    case "breaker_open":
    case "gate_unavailable":
      return { kind: "resting", until: now + wait };
    case "paused":
      return { kind: "paused" };
    case "validation":
    case "moderation":
      return { kind: "error", code: error.code, message: error.message, field: fieldOf(error) };
    default:
      return { kind: "error", code: error.code, message: error.message, field: null };
  }
}

function fieldOf(error: ApiError): "task" | "command" | null {
  if (error.code === "moderation") return "command";
  const text = error.message.toLowerCase();
  if (text.startsWith("task")) return "task";
  if (text.startsWith("command")) return "command";
  return null;
}

export function isBusy(phase: Phase): boolean {
  return phase.kind === "submitting" || phase.kind === "warming";
}

/** Seconds left on a countdown phase, at least 1 while it runs. */
export function secondsLeft(until: number, now: number): number {
  return Math.max(0, Math.ceil((until - now) / 1000));
}
