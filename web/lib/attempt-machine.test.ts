import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { isBusy, reduce, secondsLeft, type Phase } from "./attempt-machine";
import type { AttemptResult } from "./types";

const draft = { level: 1, goal_id: 1, task: "tidy", command: "rm -rf /etc" };
const result: AttemptResult = {
  attempt_id: "a1",
  approved: false,
  p_safe: 0.31,
  threshold: 0.5,
  deciding_layer: "model_a",
  layers: [],
  verified: true,
  points: 0,
  reveal_id: null,
  gate_version: "v1",
};
const submitting: Phase = { kind: "submitting", draft, key: "k1" };

function fail(code: ApiError["code"], retryAfter: number | null = null, message = "x"): Phase {
  return reduce(submitting, {
    type: "failure",
    error: new ApiError(503, code, message, retryAfter),
    now: 1_000,
  });
}

describe("attempt state machine", () => {
  it("idle -> submitting -> result", () => {
    const s1 = reduce({ kind: "idle" }, { type: "submit", draft, key: "k1" });
    expect(s1).toEqual(submitting);
    expect(reduce(s1, { type: "success", result })).toEqual({ kind: "result", result });
  });

  it("ignores a second submit while busy (no double requests)", () => {
    expect(reduce(submitting, { type: "submit", draft, key: "k2" })).toBe(submitting);
    expect(isBusy(submitting)).toBe(true);
  });

  it("a result never auto-submits; a new submit starts fresh", () => {
    const done: Phase = { kind: "result", result };
    expect(reduce(done, { type: "retry" })).toBe(done);
    expect(reduce(done, { type: "submit", draft, key: "k2" })).toEqual({
      kind: "submitting",
      draft,
      key: "k2",
    });
  });

  it("warming waits for Retry-After, then resubmits with the same key", () => {
    const warming = fail("warming_up", 45);
    expect(warming).toEqual({ kind: "warming", reason: "warming_up", retryAt: 46_000, draft, key: "k1" });
    expect(reduce(warming, { type: "retry" })).toEqual(submitting);
  });

  it("verifier_unavailable is handled like warming", () => {
    expect(fail("verifier_unavailable", 10)).toMatchObject({ kind: "warming", reason: "verifier_unavailable" });
  });

  it("an in-flight duplicate retries after 1 s", () => {
    expect(fail("idempotency_in_progress", 1)).toMatchObject({ kind: "warming", retryAt: 2_000 });
  });

  it("rate limit and resting count down from Retry-After", () => {
    expect(fail("rate_limited", 30)).toEqual({ kind: "rate_limited", until: 31_000 });
    expect(fail("breaker_open", 60)).toEqual({ kind: "resting", until: 61_000 });
    expect(fail("gate_unavailable")).toEqual({ kind: "resting", until: 11_000 });
  });

  it("paused has no countdown", () => {
    expect(fail("paused")).toEqual({ kind: "paused" });
  });

  it("validation and moderation errors point at a field", () => {
    expect(fail("validation", null, "Task is too long. The limit is 300 characters.")).toMatchObject({
      kind: "error",
      field: "task",
    });
    expect(fail("moderation", null, "This looks like a real secret")).toMatchObject({ field: "command" });
    expect(fail("network")).toMatchObject({ kind: "error", code: "network", field: null });
  });

  it("clear returns to idle from any waiting state, but not mid-request", () => {
    expect(reduce(fail("rate_limited", 5), { type: "clear" })).toEqual({ kind: "idle" });
    expect(reduce(fail("warming_up", 5), { type: "clear" })).toEqual({ kind: "idle" });
    expect(reduce(submitting, { type: "clear" })).toBe(submitting);
  });

  it("stale responses after a stop are ignored", () => {
    const idle: Phase = { kind: "idle" };
    expect(reduce(idle, { type: "success", result })).toBe(idle);
  });

  it("counts seconds down", () => {
    expect(secondsLeft(31_000, 1_000)).toBe(30);
    expect(secondsLeft(1_500, 1_000)).toBe(1);
    expect(secondsLeft(500, 1_000)).toBe(0);
  });
});
