// Per-viewer conveniences in localStorage. Every access is guarded: storage can
// be missing or throw (private windows, blocked site data), and the app must work.

const SOUND_KEY = "btg.sound";

export function readSound(): boolean {
  try {
    return window.localStorage.getItem(SOUND_KEY) === "on";
  } catch {
    return false;
  }
}

export function writeSound(on: boolean): void {
  try {
    window.localStorage.setItem(SOUND_KEY, on ? "on" : "off");
  } catch {
    // Not persisted; the in-memory toggle still works for this visit.
  }
}

let audio: AudioContext | null = null;

/** One soft mechanical click for an approval. Only called when sound is on (off by default). */
export function playClick(): void {
  try {
    audio ??= new AudioContext();
    const ctx = audio;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(1400, now);
    osc.frequency.exponentialRampToValueAtTime(520, now + 0.05);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.18, now + 0.004);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.09);
    osc.connect(gain).connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.1);
  } catch {
    // No audio: the click is a nicety, never required.
  }
}
