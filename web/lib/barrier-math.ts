// Barrier geometry (docs/PRD.md 11.4). The angle is linear and honest:
// theta = -78deg * p, where 0 is closed (horizontal) and negative is up.

export const MAX_ANGLE = 78;
export const VIEW_W = 420;
export const VIEW_H = 240;
export const PIVOT = { x: 60, y: 170 } as const;
export const ARM_LENGTH = 290;
export const ARM_THICKNESS = 22;
export const DIAL_RADIUS = 112;
export const GROUND_Y = 214;

export function clampP(p: number): number {
  if (!Number.isFinite(p)) return 0;
  return Math.min(1, Math.max(0, p));
}

/** Arm angle in degrees for a probability. null (no attempt yet) is closed. */
export function armAngle(p: number | null): number {
  if (p === null) return 0;
  const angle = -MAX_ANGLE * clampP(p);
  return angle === 0 ? 0 : angle; // never -0
}

/** A point at `radius` from the pivot along `angleDeg` (negative is up). */
export function polar(angleDeg: number, radius: number): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: PIVOT.x + radius * Math.cos(rad), y: PIVOT.y + radius * Math.sin(rad) };
}

/** SVG arc path around the pivot from angle 0 up to `toDeg` (<= 0). */
export function dialArc(toDeg: number, radius = DIAL_RADIUS): string {
  const start = polar(0, radius);
  const end = polar(toDeg, radius);
  const r = radius.toFixed(2);
  // Counter-clockwise on screen (sweep 0); never more than 78 degrees (small arc).
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${r} ${r} 0 0 0 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
}

export function fmt(p: number): string {
  return clampP(p).toFixed(2);
}

export function percent(p: number): number {
  return Math.round(clampP(p) * 100);
}

export type BarrierState = "idle" | "thinking" | "approved" | "denied" | "resting";

/** The accessible name of the barrier image (PRD 11.4). */
export function barrierLabel(p: number | null, threshold: number, state: BarrierState): string {
  const needs = `Needs ${percent(threshold)} percent.`;
  const verdict: Record<BarrierState, string> = {
    idle: "Waiting for an attempt.",
    thinking: "Deciding.",
    approved: "Approved.",
    denied: "Denied.",
    resting: "Resting.",
  };
  const prob = p === null ? "" : `Probability safe ${percent(p)} percent. `;
  return `Gate. ${prob}${needs} ${verdict[state]}`;
}
