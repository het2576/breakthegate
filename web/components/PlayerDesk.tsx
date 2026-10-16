"use client";

import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { Session } from "@/lib/types";

interface PlayerDeskProps {
  session: Session;
  onSession: (session: Session) => void;
  onDeleted: () => void;
}

export function PlayerDesk({ session, onSession, onDeleted }: PlayerDeskProps) {
  const [handle, setHandle] = useState(session.handle ?? "");
  const [consent, setConsent] = useState(session.consent_training);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const save = async () => {
    setBusy(true);
    setSaved(false);
    setMessage(null);
    try {
      const updated = await api.updateSession({ handle: handle || null, consent_training: consent });
      onSession(updated);
      setSaved(true);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : copy.network);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.deleteSession();
      onDeleted();
    } catch {
      setMessage(copy.network);
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="player-desk-title" className="rounded-field border-2 border-ink bg-white p-5" data-testid="player-desk">
      <h2 id="player-desk-title" className="sign text-xl">{copy.playerDesk}</h2>
      <label className="mt-4 block" htmlFor="player-handle">
        <span className="font-bold">{copy.handleLabel}</span>
        <input
          id="player-handle"
          value={handle}
          maxLength={20}
          onChange={(event) => {
            setHandle(event.target.value);
            setSaved(false);
          }}
          className="field mt-1"
          autoComplete="nickname"
          aria-describedby="handle-hint"
          data-testid="player-handle"
        />
        <span id="handle-hint" className="mt-1 block text-sm text-ink-soft">{copy.handleHint}</span>
      </label>

      <div className="mt-5 border-y border-fog py-4">
        <button
          type="button"
          role="switch"
          aria-checked={consent}
          aria-describedby="training-hint"
          onClick={() => {
            setConsent((value) => !value);
            setSaved(false);
          }}
          className="flex w-full items-center justify-between gap-4 text-left"
          data-testid="player-consent"
        >
          <span className="font-bold">{copy.trainingLabel}</span>
          <span aria-hidden className={`relative inline-flex h-8 w-14 shrink-0 items-center rounded-chip border-2 border-ink ${consent ? "bg-clear" : "bg-fog"}`}>
            <span className={`inline-block size-6 rounded-full border-2 border-ink bg-white ${consent ? "translate-x-6" : "translate-x-0.5"}`} />
          </span>
        </button>
        <p id="training-hint" className="mt-2 text-sm text-ink-soft">{copy.trainingHint}</p>
      </div>

      {message && <p className="mt-3 font-bold text-stamp" role="alert">{message}</p>}
      {saved && <p className="mt-3 font-bold text-clear" role="status">{copy.savedPlayer}</p>}
      <button type="button" className="btn-primary mt-5 w-full" onClick={save} disabled={busy} data-testid="save-player">
        {copy.savePlayer}
      </button>

      <div className="mt-6 border-t-2 border-stamp pt-5">
        <h3 className="sign text-lg">{copy.deleteData}</h3>
        <p className="mt-1 text-sm text-ink-soft">{copy.deleteWarning}</p>
        {confirmingDelete ? (
          <div className="mt-3 flex flex-wrap gap-3">
            <button type="button" className="btn-quiet border-stamp text-stamp" onClick={remove} disabled={busy} data-testid="confirm-delete">
              {copy.deleteConfirm}
            </button>
            <button type="button" className="btn-quiet" onClick={() => setConfirmingDelete(false)} disabled={busy}>
              {copy.deleteCancel}
            </button>
          </div>
        ) : (
          <button type="button" className="btn-quiet mt-3 border-stamp text-stamp" onClick={() => setConfirmingDelete(true)} data-testid="delete-data">
            {copy.deleteData}
          </button>
        )}
      </div>
    </section>
  );
}
