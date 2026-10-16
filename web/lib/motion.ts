// Tiny physics for the barrier arm. Angles are in degrees, time in seconds,
// mass 1. Fixed sub-steps keep the integration stable at any frame rate.

export interface Body {
  x: number; // angle
  v: number; // angular velocity
}

const SUB_STEP = 1 / 240;

/** Damped spring toward `target` (semi-implicit Euler). */
export function stepSpring(
  body: Body,
  target: number,
  stiffness: number,
  damping: number,
  dt: number,
): Body {
  let { x, v } = body;
  let remaining = Math.min(dt, 0.1); // a stalled tab should not explode the spring
  while (remaining > 0) {
    const h = Math.min(SUB_STEP, remaining);
    const a = -stiffness * (x - target) - damping * v;
    v += a * h;
    x += v * h;
    remaining -= h;
  }
  return { x, v };
}

/**
 * Falling back to the rest: spring toward 0, but the rest is a hard stop.
 * Crossing below horizontal (x > 0) bounces the arm back up with `restitution`.
 */
export function stepDrop(
  body: Body,
  stiffness: number,
  damping: number,
  restitution: number,
  dt: number,
): Body {
  const next = stepSpring(body, 0, stiffness, damping, dt);
  if (next.x > 0) {
    return { x: 0, v: -Math.abs(next.v) * restitution };
  }
  return next;
}

export function isSettled(body: Body, target: number, eps = 0.05): boolean {
  return Math.abs(body.x - target) < eps && Math.abs(body.v) < eps * 4;
}

export function easeOutCubic(t: number): number {
  const c = Math.min(1, Math.max(0, t));
  return 1 - (1 - c) ** 3;
}

// Timings and constants from PRD 11.4.
export const APPROVE_SPRING = { stiffness: 120, damping: 14 } as const;
export const DENY_RISE_MS = 500;
export const DENY_HOLD_MS = 400;
export const DROP = { stiffness: 220, damping: 6, restitution: 0.32 } as const;
export const REST_SPRING = { stiffness: 260, damping: 32 } as const;
