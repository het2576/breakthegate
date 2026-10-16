"use client";

import { useRef, useState } from "react";

import { useArmMotion } from "@/hooks/useArmMotion";
import {
  ARM_LENGTH,
  ARM_THICKNESS,
  DIAL_RADIUS,
  GROUND_Y,
  MAX_ANGLE,
  PIVOT,
  VIEW_H,
  VIEW_W,
  armAngle,
  barrierLabel,
  clampP,
  dialArc,
  fmt,
  polar,
  type BarrierState,
} from "@/lib/barrier-math";

export interface BarrierProps {
  p: number | null;
  threshold: number;
  state: BarrierState;
  reducedMotion: boolean;
  /** Changes on every new result so the same state can replay. */
  runKey?: string | number;
}

const LAMP: Record<BarrierState, string> = {
  idle: "var(--color-fog)",
  thinking: "var(--color-signal)",
  approved: "var(--color-clear)",
  denied: "var(--color-stamp)",
  resting: "var(--color-fog)",
};

const ARM_TOP = PIVOT.y - ARM_THICKNESS / 2;
const ARM_START = PIVOT.x - 10;
const ARM_END = PIVOT.x + ARM_LENGTH;
const STRIPES = 8;
const STRIPE_W = (ARM_END - ARM_START) / STRIPES;
const SKEW = 9;

function Stripes() {
  return (
    <>
      {Array.from({ length: STRIPES + 1 }, (_, i) => {
        const x0 = ARM_START - STRIPE_W + i * STRIPE_W;
        const bottom = ARM_TOP + ARM_THICKNESS;
        const points = [
          `${x0},${bottom}`,
          `${x0 + SKEW},${ARM_TOP}`,
          `${x0 + STRIPE_W + SKEW},${ARM_TOP}`,
          `${x0 + STRIPE_W},${bottom}`,
        ].join(" ");
        return (
          <polygon
            key={i}
            points={points}
            fill={i % 2 === 0 ? "var(--color-signal)" : "var(--color-ink)"}
          />
        );
      })}
    </>
  );
}

interface SceneProps extends Omit<BarrierProps, "reducedMotion"> {
  stamp: boolean;
  onStampEnd: () => void;
}

function Scene({ p, threshold, state, runKey, stamp, onStampEnd }: SceneProps) {
  const arm = useRef<SVGGElement>(null);
  useArmMotion(arm, state, p, runKey, true);

  const notch = -MAX_ANGLE * clampP(threshold);
  const notchIn = polar(notch, DIAL_RADIUS - 11);
  const notchOut = polar(notch, DIAL_RADIUS + 11);
  const label = polar(notch, DIAL_RADIUS + 20);
  const fill = p === null ? null : dialArc(armAngle(p));
  const lamp = LAMP[state];

  return (
    <svg
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      role="img"
      aria-label={barrierLabel(p, threshold, state)}
      className="mx-auto block h-[112px] w-auto md:h-auto md:w-full"
      data-testid="barrier-svg"
      data-state={state}
    >
      <defs>
        <clipPath id="arm-clip">
          <rect
            x={ARM_START}
            y={ARM_TOP}
            width={ARM_END - ARM_START}
            height={ARM_THICKNESS}
            rx={ARM_THICKNESS / 2}
          />
        </clipPath>
      </defs>

      {/* Ground: a road surface with quiet lane dashes. */}
      <rect x={0} y={GROUND_Y} width={VIEW_W} height={VIEW_H - GROUND_Y} fill="var(--color-paper)" />
      <line
        x1={128}
        x2={VIEW_W}
        y1={GROUND_Y + 13}
        y2={GROUND_Y + 13}
        stroke="var(--color-fog)"
        strokeWidth={4}
        strokeDasharray="20 16"
        strokeLinecap="round"
      />
      <line x1={0} x2={VIEW_W} y1={GROUND_Y} y2={GROUND_Y} stroke="var(--color-ink)" strokeWidth={2} />

      {/* Dial: track, fill to p, threshold notch. Honest and linear. */}
      <path d={dialArc(-MAX_ANGLE)} fill="none" stroke="var(--color-fog)" strokeWidth={5} strokeLinecap="round" />
      {fill && (
        <path
          d={fill}
          fill="none"
          stroke="var(--color-cobalt)"
          strokeWidth={5}
          strokeLinecap="round"
          opacity={state === "thinking" ? 0.35 : 1}
          data-testid="dial-fill"
        />
      )}
      <line
        x1={notchIn.x}
        y1={notchIn.y}
        x2={notchOut.x}
        y2={notchOut.y}
        stroke="var(--color-ink)"
        strokeWidth={3}
        strokeLinecap="round"
      />
      <text
        x={label.x}
        y={label.y}
        dominantBaseline="middle"
        className="sign-narrow figures max-md:hidden"
        fontSize={15}
        fill="var(--color-ink-soft)"
      >
        needs {fmt(threshold)}
      </text>

      {/* The arm: rotated by JS around the pivot; trembles in CSS while thinking. */}
      <g ref={arm} transform={`rotate(0 ${PIVOT.x} ${PIVOT.y})`} data-testid="barrier-arm" data-angle="0.00">
        <g
          className={state === "thinking" ? "animate-tremble" : undefined}
          style={{ transformBox: "view-box", transformOrigin: `${PIVOT.x}px ${PIVOT.y}px` }}
        >
          <rect x={PIVOT.x - 42} y={PIVOT.y - 10} width={32} height={20} rx={4} fill="var(--color-ink)" />
          <g clipPath="url(#arm-clip)">
            <Stripes />
          </g>
          <rect
            x={ARM_START}
            y={ARM_TOP}
            width={ARM_END - ARM_START}
            height={ARM_THICKNESS}
            rx={ARM_THICKNESS / 2}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth={2.5}
          />
        </g>
      </g>
      {/* Cabinet in front of the arm: the arm comes out of it, like a real gate. The
          lamp sits on the cabinet face below the hinge, where the arm never covers it. */}
      <rect x={PIVOT.x - 24} y={146} width={48} height={GROUND_Y - 146} rx={7} fill="var(--color-ink)" />
      <rect x={PIVOT.x - 34} y={GROUND_Y - 3} width={68} height={5} rx={2} fill="var(--color-ink)" />
      <circle
        cx={PIVOT.x}
        cy={198}
        r={15}
        fill={lamp}
        opacity={state === "idle" || state === "resting" ? 0 : 0.35}
      />
      <circle
        cx={PIVOT.x}
        cy={198}
        r={8.5}
        fill={lamp}
        stroke="var(--color-paper)"
        strokeWidth={2}
        data-testid="lamp"
        data-lamp={state}
      />
      <circle cx={PIVOT.x} cy={PIVOT.y} r={13} fill="var(--color-paper)" stroke="var(--color-ink)" strokeWidth={3} />
      <circle cx={PIVOT.x} cy={PIVOT.y} r={4} fill="var(--color-ink)" />

      {/* The stamp sits just above the ground on the right: the one place the arm
          never passes at any angle. Inside the SVG, so it scales with the scene. */}
      {stamp && (
        <g
          key={runKey}
          aria-hidden
          className="animate-stamp"
          style={{ transformBox: "fill-box", transformOrigin: "center", opacity: 0 }}
          onAnimationEnd={onStampEnd}
          data-testid="denied-stamp"
        >
          <rect x={268} y={180} width={136} height={30} rx={5} fill="rgb(255 255 255 / 0.88)" stroke="var(--color-stamp)" strokeWidth={3} />
          <text x={336} y={196} textAnchor="middle" dominantBaseline="central" className="sign" fontSize={21} fill="var(--color-stamp)">
            Denied
          </text>
        </g>
      )}
    </svg>
  );
}

/** Reduced motion: a striped bar filled to p with a threshold tick (PRD 11.4). */
function Meter({ p, threshold, state }: Omit<BarrierProps, "reducedMotion" | "runKey">) {
  const width = p === null ? 0 : clampP(p) * 100;
  return (
    <div
      role="img"
      aria-label={barrierLabel(p, threshold, state)}
      data-testid="barrier-meter"
      data-state={state}
      className="px-4 pt-6 pb-2 md:px-8 md:pt-10"
    >
      <div className="relative h-7 overflow-hidden rounded-field border-2 border-ink bg-paper">
        <div
          className="h-full border-r-2 border-ink"
          style={{
            width: `${width}%`,
            background:
              "repeating-linear-gradient(-60deg, var(--color-signal) 0 14px, var(--color-ink) 14px 28px)",
            borderRightWidth: width === 0 ? 0 : 2,
          }}
        />
      </div>
      <div className="relative mt-1 h-6">
        <span
          className="absolute top-0 flex -translate-x-1/2 flex-col items-center"
          style={{ left: `${clampP(threshold) * 100}%` }}
        >
          <span className="block h-2 w-[3px] bg-ink" aria-hidden />
          <span className="sign-narrow figures text-sm whitespace-nowrap text-ink-soft">
            needs {fmt(threshold)}
          </span>
        </span>
      </div>
    </div>
  );
}

function Verdict({ state }: { state: BarrierState }) {
  if (state === "approved") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-chip bg-clear px-3 py-1 font-bold text-white">
        <svg viewBox="0 0 16 16" className="size-4" aria-hidden>
          <path d="M3 8.5l3.2 3.2L13 5" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Approved
      </span>
    );
  }
  if (state === "denied") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-chip bg-stamp px-3 py-1 font-bold text-white">
        <svg viewBox="0 0 16 16" className="size-4" aria-hidden>
          <path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" />
        </svg>
        Denied
      </span>
    );
  }
  const text = { idle: "Ready", thinking: "Deciding", resting: "Resting" }[state];
  return (
    <span className="inline-flex items-center gap-2 rounded-chip border-2 border-ink bg-white px-3 py-0.5 font-bold">
      <span
        aria-hidden
        className="size-2.5 rounded-full border border-ink"
        style={{ background: LAMP[state] }}
      />
      {text}
    </span>
  );
}

/** The boom barrier: scene (or reduced-motion meter) plus the readout under it. */
export function Barrier({ p, threshold, state, reducedMotion, runKey }: BarrierProps) {
  const showNumber = p !== null && state !== "idle";
  // The stamp plays once per result: showing the same result again stays quiet.
  const [stamped, setStamped] = useState<string | number | undefined>(undefined);
  const showStamp = state === "denied" && !reducedMotion && runKey !== undefined && stamped !== runKey;
  return (
    <figure className="relative overflow-hidden rounded-housing border-2 border-ink bg-white" data-testid="barrier">
      {reducedMotion ? (
        <Meter p={p} threshold={threshold} state={state} />
      ) : (
        <Scene
          p={p}
          threshold={threshold}
          state={state}
          runKey={runKey}
          stamp={showStamp}
          onStampEnd={() => setStamped(runKey)}
        />
      )}


      <figcaption className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 border-t-2 border-ink bg-white px-3 py-2 md:py-3">
        {/* No attempt yet: keep the width (no layout shift) but show nothing false. */}
        <span
          className={`sign figures text-2xl leading-none md:text-3xl ${
            showNumber ? (state === "thinking" ? "text-ink-soft" : "text-ink") : "invisible"
          }`}
          data-testid="readout-p"
        >
          {showNumber ? fmt(p) : "0.00"}
        </span>
        <span className="sign-narrow figures text-base text-ink-soft md:text-lg">needs {fmt(threshold)}</span>
        <Verdict state={state} />
      </figcaption>
    </figure>
  );
}
