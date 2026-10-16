"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import Link from "next/link";

import { useReducedMotion } from "@/hooks/useReducedMotion";
import { ApiError, api, newIdempotencyKey } from "@/lib/api";
import { isBusy, reduce, type Phase } from "@/lib/attempt-machine";
import type { BarrierState } from "@/lib/barrier-math";
import { copy } from "@/lib/copy";
import { playClick, readSound, writeSound } from "@/lib/prefs";
import type { AttemptDraft, AttemptResult, HistoryItem, LeaderboardEntry, LevelsResponse, Session } from "@/lib/types";

import { AttemptTimeline } from "./AttemptTimeline";
import { Barrier } from "./Barrier";
import { Checks } from "./Checks";
import { Composer } from "./Composer";
import { ConsentSheet } from "./ConsentSheet";
import { Header, PANEL_ID, tabId } from "./Header";
import { HowToPlay } from "./HowToPlay";
import { LockIcon } from "./icons";
import { Leaderboard } from "./Leaderboard";
import { PlayerDesk } from "./PlayerDesk";
import { StatusLine } from "./StatusLine";
import { VaultTeaser } from "./VaultTeaser";
import { WinReveal } from "./WinReveal";

type FieldErrors = { task?: string; command?: string };

function toHistory(result: AttemptResult, draft: AttemptDraft): HistoryItem {
  return {
    attempt_id: result.attempt_id,
    level: draft.level,
    goal_id: draft.goal_id,
    task: draft.task,
    command: draft.command,
    approved: result.approved,
    p_safe: result.p_safe,
    threshold: result.threshold,
    deciding_layer: result.deciding_layer,
    layers: result.layers,
    verified: result.verified,
    points: result.points,
    gate_version: result.gate_version,
    created_at: new Date().toISOString(),
  };
}

function Footer({ version }: { version?: string }) {
  return (
    <footer className="mt-auto border-t-2 border-ink bg-white">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 py-5 sm:px-6 lg:px-8">
        <p className="font-bold">{copy.neverExecuted}</p>
        <div className="flex items-baseline gap-5">
          <Link href="/report" className="font-bold underline underline-offset-4">Gate report</Link>
          <Link href="/privacy" className="font-bold underline underline-offset-4">{copy.privacy}</Link>
          {version && <p className="figures text-sm text-ink-soft">Gate version {version}</p>}
        </div>
      </div>
    </footer>
  );
}

function Loading({ error }: { error: string | null }) {
  return (
    <div className="grid gap-8 py-8 md:grid-cols-12 lg:py-12" aria-busy={!error}>
      <div className="space-y-4 md:col-span-6 lg:col-span-5">
        <div className="h-8 w-2/3 rounded-field bg-fog" />
        <div className="h-24 rounded-field bg-fog" />
        <div className="h-20 rounded-field bg-fog" />
        <div className="h-28 rounded-field bg-fog" />
      </div>
      <div className="md:col-span-6 lg:col-span-7">
        <div className="flex aspect-[7/5] items-center justify-center rounded-housing border-2 border-ink bg-white px-6 text-center">
          {error ? (
            <div>
              <p className="font-bold text-stamp">{error}</p>
              <button type="button" className="btn-quiet mt-4" onClick={() => window.location.reload()}>
                {copy.tryAgain}
              </button>
            </div>
          ) : (
            <p className="sign-narrow text-lg text-ink-soft">{copy.loading}</p>
          )}
        </div>
      </div>
    </div>
  );
}

export function Game() {
  const reducedMotion = useReducedMotion();
  const [data, setData] = useState<LevelsResponse | null>(null);
  const [howOpen, setHowOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null | undefined>(undefined); // undefined: not known yet
  const [level, setLevel] = useState(1);
  const [goalId, setGoalId] = useState(1);
  const [task, setTask] = useState("");
  const [command, setCommand] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [phase, dispatch] = useReducer(reduce, { kind: "idle" } as Phase);
  const [last, setLast] = useState<AttemptResult | null>(null);
  const [revealId, setRevealId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [sound, setSound] = useState(false);
  const [now, setNow] = useState(0); // set by the countdown interval; never read before a countdown starts
  const soundRef = useRef(false);
  const sentFor = useRef<Phase | null>(null);

  // Load levels and the session once.
  useEffect(() => {
    let alive = true;
    Promise.all([api.levels(), api.me()])
      .then(([levels, me]) => {
        if (!alive) return;
        setData(levels);
        setSession(me);
        const first = levels.levels.find((l) => !l.locked);
        if (first) setLevel(first.level);
        const on = readSound();
        soundRef.current = on;
        setSound(on);
      })
      .catch(() => alive && setLoadError(copy.network));
    return () => {
      alive = false;
    };
  }, []);

  // History for the current level, once a session exists.
  useEffect(() => {
    if (!session || !data) return;
    let alive = true;
    api
      .history(level)
      .then((h) => alive && setHistory(h.attempts))
      .catch(() => alive && setHistory([]));
    return () => {
      alive = false;
    };
  }, [session, level, data]);

  useEffect(() => {
    if (!data) return;
    let alive = true;
    api.leaderboard(level).then((board) => alive && setLeaderboard(board.entries)).catch(() => alive && setLeaderboard([]));
    return () => {
      alive = false;
    };
  }, [data, level, history]);

  // Send whenever the machine enters "submitting" (first try or a warming retry).
  // Deduplicated by phase identity, so StrictMode's double effect sends once.
  useEffect(() => {
    if (phase.kind !== "submitting" || sentFor.current === phase) return;
    sentFor.current = phase;
    const { draft, key } = phase;
    api
      .attempt(draft, key)
      .then((result) => {
        setLast(result);
        setHistory((h) => [toHistory(result, draft), ...h.filter((x) => x.attempt_id !== result.attempt_id)]);
        if (result.approved && soundRef.current) playClick();
        if (result.reveal_id) setRevealId(result.reveal_id);
        dispatch({ type: "success", result });
      })
      .catch((err: unknown) => {
        const error = err instanceof ApiError ? err : new ApiError(0, "network", copy.network);
        if (error.code === "moderation") setErrors({ command: error.message });
        if (error.code === "validation") {
          const field = error.message.toLowerCase().startsWith("task") ? "task" : "command";
          setErrors({ [field]: error.message });
        }
        if (error.code === "no_session") setSession(null);
        dispatch({ type: "failure", error, now: Date.now() });
      });
  }, [phase]);

  // Warming: wait for Retry-After, then resubmit with the same key.
  useEffect(() => {
    if (phase.kind !== "warming") return;
    const timer = window.setTimeout(() => dispatch({ type: "retry" }), Math.max(0, phase.retryAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [phase]);

  // Countdowns tick; rate limits and resting clear themselves when they run out.
  useEffect(() => {
    if (phase.kind !== "warming" && phase.kind !== "rate_limited" && phase.kind !== "resting") return;
    const timer = window.setInterval(() => {
      const t = Date.now();
      setNow(t);
      if ((phase.kind === "rate_limited" || phase.kind === "resting") && t >= phase.until) {
        dispatch({ type: "clear" });
      }
    }, 250);
    return () => window.clearInterval(timer);
  }, [phase]);

  const busy = isBusy(phase);
  const current = data?.levels.find((l) => l.level === level);
  const locked = current?.locked ?? false;

  const submit = useCallback(() => {
    const next: FieldErrors = {};
    if (!task.trim()) next.task = "Write what the agent says it is doing.";
    if (!command.trim()) next.command = "Write the command to run.";
    setErrors(next);
    if (next.task || next.command) return;
    dispatch({ type: "submit", draft: { level, goal_id: goalId, task, command }, key: newIdempotencyKey() });
  }, [level, goalId, task, command]);

  const changeLevel = (next: number) => {
    if (busy || next === level) return;
    setLevel(next);
    setLast(null);
    setHistory([]);
    setErrors({});
    setRevealId(null);
    dispatch({ type: "clear" });
  };

  const toggleSound = (on: boolean) => {
    soundRef.current = on;
    setSound(on);
    writeSound(on);
  };

  const startSession = async (consent: boolean, turnstileToken?: string | null) => {
    setSession(await api.startSession(consent, turnstileToken));
    dispatch({ type: "clear" });
  };

  // What the barrier shows. A failed request falls back to the last result,
  // which the barrier settles into without replaying its animation.
  const shown = phase.kind === "result" ? phase.result : last;
  const defaultTau = current?.layers.find((l) => l.threshold !== null)?.threshold ?? 0.5;
  const barrierState: BarrierState =
    busy ? "thinking"
    : locked || phase.kind === "resting" || phase.kind === "paused" ? "resting"
    : shown ? (shown.approved ? "approved" : "denied")
    : "idle";
  const threshold = shown && shown.threshold > 0 ? shown.threshold : defaultTau;

  return (
    <>
      <Header levels={data?.levels ?? []} level={level} onLevel={changeLevel} sound={sound} onSound={toggleSound} onHow={() => setHowOpen(true)} />
      <HowToPlay open={howOpen} onClose={() => setHowOpen(false)} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 sm:px-6 lg:px-8">
        {!data || !current ? (
          <Loading error={loadError} />
        ) : (
          <div
            role="tabpanel"
            id={PANEL_ID}
            aria-labelledby={tabId(level)}
            className="grid grid-cols-1 gap-y-6 pt-0 pb-10 md:grid-cols-12 md:grid-rows-[auto_auto_auto_1fr_auto] md:gap-x-8 md:gap-y-8 md:pt-8 lg:gap-x-12 lg:pt-10"
          >
            {/* Barrier first in the DOM: sticky on phones (PRD 11.3). */}
            <div className="sticky top-0 z-20 -mx-4 bg-paper/95 px-4 pt-3 pb-2 backdrop-blur-sm sm:-mx-6 sm:px-6 md:static md:col-span-6 md:col-start-7 lg:col-span-7 lg:col-start-6 md:row-start-1 md:mx-0 md:bg-transparent md:p-0 md:backdrop-blur-none">
              <Barrier
                p={shown?.p_safe ?? null}
                threshold={threshold}
                state={barrierState}
                reducedMotion={reducedMotion}
                runKey={shown?.attempt_id}
              />
            </div>

            <div className="md:col-span-6 md:col-start-7 lg:col-span-7 lg:col-start-6 md:row-start-2">
              <StatusLine
                phase={phase}
                last={last}
                now={now}
                onStop={() => dispatch({ type: "clear" })}
                onRetry={submit}
                onNewSession={() => setSession(null)}
              />
            </div>

            <div className="md:sticky md:top-6 md:col-span-6 md:col-start-1 lg:col-span-5 md:row-span-4 md:row-start-1 md:self-start">
              <div className="mb-6 border-b-2 border-ink pb-4">
                <p className="sign-narrow figures text-ink-soft">Level {current.level}</p>
                <h2 className="sign text-2xl sm:text-3xl" data-testid="level-name">
                  {current.name}
                </h2>
                <p className="mt-2 text-ink">
                  {current.rule}{" "}
                  <span className="text-ink-soft">{current.layers.map((l) => l.label).join(", then ")}.</span>
                </p>
              </div>

              <VaultTeaser level={current.level} tried={current.players_tried} winners={current.winners} />

              {locked ? (
                <div className="rounded-field border-2 border-ink bg-white px-5 py-6" data-testid="locked">
                  <p className="flex items-center gap-2 font-bold">
                    <LockIcon className="size-5" />
                    {current.locked_text ?? copy.levelLocked}
                  </p>
                  <p className="mt-2 text-ink-soft">
                    This gate is trained on attempts from levels 1 to 4. Beat those while you wait.
                  </p>
                </div>
              ) : (
                <Composer
                  goals={data.goals}
                  goalId={goalId}
                  task={task}
                  command={command}
                  onGoal={setGoalId}
                  onTask={(v) => {
                    setTask(v);
                    if (errors.task) setErrors((e) => ({ ...e, task: undefined }));
                  }}
                  onCommand={(v) => {
                    setCommand(v);
                    if (errors.command) setErrors((e) => ({ ...e, command: undefined }));
                  }}
                  onSubmit={submit}
                  busy={busy}
                  disabled={!session}
                  errors={errors}
                />
              )}

              {session && (
                <div className="mt-8">
                  <PlayerDesk
                    session={session}
                    onSession={(updated) => setSession(updated)}
                    onDeleted={() => {
                      setSession(null);
                      setHistory([]);
                      setLast(null);
                    }}
                  />
                </div>
              )}
            </div>

            <div className="md:col-span-6 md:col-start-7 lg:col-span-7 lg:col-start-6 md:row-start-3">
              <Checks layers={current.layers} result={shown} goalCheck={data.goal_check} />
            </div>

            <div className="md:col-span-6 md:col-start-7 lg:col-span-7 lg:col-start-6 md:row-start-4">
              <AttemptTimeline history={history} threshold={defaultTau} goals={data.goals} />
            </div>

            <div className="md:col-span-6 md:col-start-7 lg:col-span-7 lg:col-start-6 md:row-start-5">
              <Leaderboard entries={leaderboard} level={level} />
            </div>
          </div>
        )}
      </main>

      <Footer version={data?.gate_version} />
      {data && session === null && <ConsentSheet onStart={startSession} />}
      {revealId && (
        <WinReveal
          revealId={revealId}
          reducedMotion={reducedMotion}
          sound={sound}
          onDone={() => setRevealId(null)}
        />
      )}
    </>
  );
}
