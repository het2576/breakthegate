// Shapes of the API responses (docs/PRD.md section 7). Mirrors api/app/routes.

export type LayerKind = "rule_floor" | "model" | "task_match";

export interface PublicLayer {
  name: string;
  label: string;
  kind: LayerKind;
  question: string | null;
  threshold: number | null;
  description: string | null;
}

export interface Level {
  level: number;
  name: string;
  locked: boolean;
  locked_text: string | null;
  rule: string;
  layers: PublicLayer[];
  players_tried: number;
  winners: number;
}

export interface Goal {
  id: number;
  text: string;
}

export interface LevelsResponse {
  gate_version: string;
  levels: Level[];
  goals: Goal[];
  goal_check: { question: string; threshold: number; description: string };
}

export interface Session {
  handle: string | null;
  consent_training: boolean;
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  handle: string;
  score: number;
  attempts: number;
}

export interface LeaderboardResponse {
  level: number;
  entries: LeaderboardEntry[];
}

export interface Interval {
  v: number;
  lo: number;
  hi: number;
}

export interface ReportModel {
  name: string;
  tau: number;
  asr: Record<string, Interval>;
  fbr: Record<string, Interval>;
  auroc?: number;
  brier?: number;
  ece?: number;
  n: { dangerous: number; safe: number };
}

export interface GateReport {
  gate_version: string;
  date?: string;
  models: ReportModel[];
  limits: string[];
  file_hash?: string;
}

export interface LayerResult {
  name: string;
  passed: boolean;
  p_safe: number | null;
  detail: string;
}

export interface AttemptResult {
  attempt_id: string;
  approved: boolean;
  p_safe: number;
  threshold: number;
  deciding_layer: string;
  layers: LayerResult[];
  verified: boolean | null;
  points: number;
  reveal_id: string | null;
  gate_version: string;
}

export interface RevealClaim {
  variant: "standard" | "legendary";
  level: number;
  attempts: number;
  seconds: number;
  badge: string;
  video_id: string | null;
}

export interface HistoryItem {
  attempt_id: string;
  level: number;
  goal_id: number;
  task: string;
  command: string;
  approved: boolean;
  p_safe: number;
  threshold: number;
  deciding_layer: string;
  layers: LayerResult[];
  verified: boolean | null;
  points: number;
  gate_version: string;
  created_at: string;
}

export interface HistoryResponse {
  attempts: HistoryItem[];
  next_before: string | null;
}

export interface AttemptDraft {
  level: number;
  goal_id: number;
  task: string;
  command: string;
}

export type ErrorCode =
  | "forbidden"
  | "no_session"
  | "validation"
  | "moderation"
  | "level_locked"
  | "idempotency_key_reused"
  | "idempotency_in_progress"
  | "already_claimed"
  | "reveal_expired"
  | "rate_limited"
  | "warming_up"
  | "verifier_unavailable"
  | "gate_unavailable"
  | "breaker_open"
  | "paused"
  | "not_found"
  | "network"
  | "unknown";
