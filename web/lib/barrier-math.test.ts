import { describe, expect, it } from "vitest";

import { armAngle, barrierLabel, clampP, dialArc, fmt, percent, polar, PIVOT } from "./barrier-math";
import {
  APPROVE_SPRING,
  DROP,
  easeOutCubic,
  isSettled,
  stepDrop,
  stepSpring,
  type Body,
} from "./motion";

describe("armAngle: theta = -78deg * p, linear and honest", () => {
  it.each([
    [0, 0],
    [0.5, -39],
    [1, -78],
    [0.31, -24.18],
  ])("p=%s gives %s degrees", (p, expected) => {
    expect(armAngle(p)).toBeCloseTo(expected, 6);
  });

  it("is closed with no attempt and clamps out-of-range input", () => {
    expect(armAngle(null)).toBe(0);
    expect(Object.is(armAngle(0), -0)).toBe(false);
    expect(armAngle(1.7)).toBe(-78);
    expect(armAngle(-0.2)).toBe(0);
    expect(armAngle(Number.NaN)).toBe(0);
  });

  it("is linear: equal steps in p are equal steps in angle", () => {
    const a = armAngle(0.2) - armAngle(0.1);
    const b = armAngle(0.9) - armAngle(0.8);
    expect(a).toBeCloseTo(b, 9);
  });
});

describe("dial geometry", () => {
  it("measures angles from the pivot, negative is up", () => {
    expect(polar(0, 100)).toEqual({ x: PIVOT.x + 100, y: PIVOT.y });
    const up = polar(-90, 100);
    expect(up.x).toBeCloseTo(PIVOT.x, 9);
    expect(up.y).toBeCloseTo(PIVOT.y - 100, 9);
  });

  it("draws a small counter-clockwise arc", () => {
    expect(dialArc(-39)).toMatch(/^M 172\.00 170\.00 A 112\.00 112\.00 0 0 0 /);
  });
});

describe("formatting and the accessible name", () => {
  it("formats probabilities", () => {
    expect(fmt(0.314)).toBe("0.31");
    expect(percent(0.6)).toBe(60);
    expect(clampP(2)).toBe(1);
  });

  it("speaks the PRD sentence", () => {
    expect(barrierLabel(0.31, 0.6, "denied")).toBe(
      "Gate. Probability safe 31 percent. Needs 60 percent. Denied.",
    );
    expect(barrierLabel(null, 0.5, "idle")).toBe("Gate. Needs 50 percent. Waiting for an attempt.");
  });
});

function run(step: (b: Body) => Body, start: Body, seconds: number): Body[] {
  const frames: Body[] = [start];
  let b = start;
  for (let i = 0; i < Math.round(seconds * 60); i += 1) {
    b = step(b);
    frames.push(b);
  }
  return frames;
}

describe("motion", () => {
  it("the approve spring settles fully open within 1.5 s and overshoots a little", () => {
    const frames = run(
      (b) => stepSpring(b, -78, APPROVE_SPRING.stiffness, APPROVE_SPRING.damping, 1 / 60),
      { x: 0, v: 0 },
      1.5,
    );
    const last = frames.at(-1)!;
    expect(isSettled(last, -78, 0.5)).toBe(true);
    const peak = Math.min(...frames.map((f) => f.x));
    expect(peak).toBeLessThan(-78); // a spring, not a tween
    expect(peak).toBeGreaterThan(-90); // but only a little
  });

  it("the drop bounces on the rest and never goes below horizontal", () => {
    const frames = run(
      (b) => stepDrop(b, DROP.stiffness, DROP.damping, DROP.restitution, 1 / 60),
      { x: -24, v: 0 },
      2,
    );
    expect(Math.max(...frames.map((f) => f.x))).toBeLessThanOrEqual(0);
    const rebounds = frames.filter((f, i) => i > 0 && f.v < 0 && frames[i - 1]!.v >= 0).length;
    expect(rebounds).toBeGreaterThanOrEqual(1); // at least one visible bounce
    expect(isSettled(frames.at(-1)!, 0, 0.2)).toBe(true);
  });

  it("a stalled frame does not explode the integration", () => {
    const b = stepSpring({ x: 0, v: 0 }, -78, 120, 14, 5);
    expect(Number.isFinite(b.x)).toBe(true);
    expect(b.x).toBeGreaterThan(-100);
  });

  it("eases out and clamps", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
    expect(easeOutCubic(0.5)).toBeCloseTo(0.875, 9);
    expect(easeOutCubic(2)).toBe(1);
  });
});
