"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { RevealClaim } from "@/lib/types";

type Stage = "vault" | "claiming" | "gift" | "dance" | "ready" | "video" | "complete" | "error";

interface WinRevealProps {
  revealId: string;
  reducedMotion: boolean;
  sound: boolean;
  onDone: () => void;
}

function duration(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, seconds)} seconds`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} minutes ${rest} seconds` : `${minutes} minutes`;
}

function BarrierDance({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <div className={`reveal-dance ${reducedMotion ? "reveal-dance-still" : ""}`} aria-hidden="true">
      <div className="reveal-dance-post" />
      <div className="reveal-dance-arm">
        {Array.from({ length: 8 }, (_, index) => (
          <span key={index} />
        ))}
      </div>
      <div className="reveal-dance-lamp" />
    </div>
  );
}

/** A session-bound finale. The video element does not exist until the player asks for it. */
export function WinReveal({ revealId, reducedMotion, sound, onDone }: WinRevealProps) {
  const [stage, setStage] = useState<Stage>("vault");
  const [win, setWin] = useState<RevealClaim | null>(null);
  const [message, setMessage] = useState("");
  const opener = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    opener.current?.focus();
  }, []);

  useEffect(() => {
    if (stage !== "gift") return;
    const timer = window.setTimeout(() => setStage(reducedMotion ? "ready" : "dance"), 1100);
    return () => window.clearTimeout(timer);
  }, [reducedMotion, stage]);

  useEffect(() => {
    if (stage !== "dance") return;
    const timer = window.setTimeout(() => setStage("ready"), 4000);
    return () => window.clearTimeout(timer);
  }, [stage]);

  const openVault = async () => {
    setStage("claiming");
    try {
      const result = await api.claimReveal(revealId);
      setWin(result);
      setStage(reducedMotion ? "ready" : "gift");
      if (sound) navigator.vibrate?.(30);
    } catch (error) {
      const expired = error instanceof ApiError && error.code === "reveal_expired";
      setMessage(expired ? copy.revealExpired : copy.revealUnavailable);
      setStage("error");
    }
  };

  const finished = stage === "complete" && win;

  return (
    <div className="reveal-backdrop" role="presentation">
      <section
        className="reveal-cabinet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reveal-title"
        aria-describedby="reveal-description"
        data-testid="win-reveal"
      >
        <div className="reveal-topline">
          <span className="sign-narrow figures">Level {win?.level ?? ""}</span>
          <button type="button" className="btn-quiet" onClick={onDone} data-testid="reveal-skip">
            {copy.skip}
          </button>
        </div>

        {stage === "vault" || stage === "claiming" ? (
          <div className="reveal-stage reveal-vault-stage">
            <div className="reveal-vault" aria-hidden="true">
              <span className="reveal-vault-handle" />
              <span className="reveal-vault-wheel">+</span>
            </div>
            <h2 id="reveal-title" className="sign text-2xl sm:text-3xl">
              {copy.vaultTitle}
            </h2>
            <p id="reveal-description" className="max-w-[38ch] text-ink-soft">
              Your verified win opened the checkpoint cabinet.
            </p>
            <button
              ref={opener}
              type="button"
              className="btn-primary"
              onClick={openVault}
              disabled={stage === "claiming"}
              data-testid="open-vault"
            >
              {stage === "claiming" ? "Opening the vault" : copy.vaultButton}
            </button>
          </div>
        ) : null}

        {stage === "gift" ? (
          <div className="reveal-stage" aria-live="polite">
            <div className="gift-box gift-box-shake" aria-hidden="true">
              <span className="gift-ribbon" />
              <span className="gift-lid" />
            </div>
            <p id="reveal-description" className="sign text-xl">
              Checking the seal
            </p>
          </div>
        ) : null}

        {stage === "dance" ? (
          <div className="reveal-stage" aria-live="polite">
            <BarrierDance reducedMotion={false} />
            <p id="reveal-description" className="sign text-xl">
              {copy.danceCaption}
            </p>
          </div>
        ) : null}

        {stage === "ready" ? (
          <div className="reveal-stage" aria-live="polite">
            <BarrierDance reducedMotion={reducedMotion} />
            <h2 id="reveal-title" className="sign text-2xl">
              The gate has a message for you.
            </h2>
            <button type="button" className="btn-primary" onClick={() => setStage("video")} data-testid="open-gift">
              {copy.giftButton}
            </button>
          </div>
        ) : null}

        {stage === "video" ? (
          <div className="reveal-stage reveal-video-stage">
            {win?.video_id ? (
              <iframe
                className="reveal-video"
                src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(win.video_id)}?autoplay=1&rel=0`}
                title="Your reward"
                allow="autoplay; encrypted-media; picture-in-picture"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
                data-testid="reveal-iframe"
              />
            ) : (
              <video
                className="reveal-video"
                controls
                playsInline
                preload="none"
                onEnded={() => setStage("complete")}
                data-testid="reveal-video"
              >
                <source src="/rickroll.mp4" type="video/mp4" />
                Your browser does not support video playback.
              </video>
            )}
            <button type="button" className="btn-quiet" onClick={() => setStage("complete")}>
              Continue
            </button>
          </div>
        ) : null}

        {finished ? (
          <div className="reveal-stage" aria-live="polite">
            <p className="reveal-badge">{win.badge}</p>
            <h2 id="reveal-title" className="sign text-2xl sm:text-3xl">
              You got through.
            </h2>
            <p id="reveal-description" className="max-w-[38ch] text-ink-soft">
              {copy.congrats(win.level, win.attempts, duration(win.seconds))}
            </p>
            {win.variant === "legendary" && <p className="font-bold text-clear">{copy.legendary(1)}</p>}
            <button type="button" className="btn-primary" onClick={onDone}>
              Keep playing
            </button>
          </div>
        ) : null}

        {stage === "error" ? (
          <div className="reveal-stage" aria-live="assertive">
            <h2 id="reveal-title" className="sign text-2xl">
              {message}
            </h2>
            <button type="button" className="btn-primary" onClick={onDone}>
              Keep playing
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
