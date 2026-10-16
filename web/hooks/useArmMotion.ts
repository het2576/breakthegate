"use client";

import { useEffect, useRef, type RefObject } from "react";

import { armAngle, MAX_ANGLE, PIVOT, type BarrierState } from "@/lib/barrier-math";
import {
  APPROVE_SPRING,
  DENY_HOLD_MS,
  DENY_RISE_MS,
  DROP,
  REST_SPRING,
  easeOutCubic,
  isSettled,
  stepDrop,
  stepSpring,
  type Body,
} from "@/lib/motion";

function write(el: SVGGElement, angle: number): void {
  el.setAttribute("transform", `rotate(${angle.toFixed(3)} ${PIVOT.x} ${PIVOT.y})`);
  el.dataset.angle = angle.toFixed(2);
}

/**
 * Drives the arm group's rotation with requestAnimationFrame, writing the
 * transform directly so React does not re-render every frame. The angle lives
 * in a ref, so each new state starts from wherever the arm actually is.
 */
export function useArmMotion(
  arm: RefObject<SVGGElement | null>,
  state: BarrierState,
  p: number | null,
  runKey: string | number | undefined,
  enabled: boolean,
): void {
  const body = useRef<Body>({ x: 0, v: 0 });
  // The result whose sequence already played. Showing the same result again
  // (after a rate limit or a failed retry) settles in place instead of replaying.
  const played = useRef<string | number | undefined>(undefined);

  useEffect(() => {
    const el = arm.current;
    if (!el || !enabled) return;

    const fresh = runKey !== played.current;
    if (state === "approved" || state === "denied") played.current = runKey;
    const replayDenied = state === "denied" && fresh;

    const from = body.current.x;
    const target = armAngle(p);
    const started = performance.now();
    let last = started;
    let frame = 0;

    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      const t = now - started;
      last = now;
      let b = body.current;
      let done = false;

      switch (state) {
        case "approved":
          b = stepSpring(b, -MAX_ANGLE, APPROVE_SPRING.stiffness, APPROVE_SPRING.damping, dt);
          done = isSettled(b, -MAX_ANGLE);
          break;
        case "denied":
          if (!replayDenied) {
            b = stepSpring(b, 0, REST_SPRING.stiffness, REST_SPRING.damping, dt);
            done = isSettled(b, 0);
          } else if (t < DENY_RISE_MS) {
            b = { x: from + (target - from) * easeOutCubic(t / DENY_RISE_MS), v: 0 };
          } else if (t < DENY_RISE_MS + DENY_HOLD_MS) {
            b = { x: target, v: 0 };
          } else {
            b = stepDrop(b, DROP.stiffness, DROP.damping, DROP.restitution, dt);
            done = isSettled(b, 0);
          }
          break;
        case "thinking":
          done = true; // hold the last angle; the tremble is CSS on an inner group
          break;
        case "idle":
        case "resting":
          b = stepSpring(b, 0, REST_SPRING.stiffness, REST_SPRING.damping, dt);
          done = isSettled(b, 0);
          break;
      }

      if (done && state !== "thinking") {
        b = { x: state === "approved" ? -MAX_ANGLE : 0, v: 0 };
      }
      body.current = b;
      write(el, b.x);
      if (!done) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [arm, state, p, runKey, enabled]);
}
