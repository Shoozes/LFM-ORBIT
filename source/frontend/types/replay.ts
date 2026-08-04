export type ReplayComparisonRow = {
  cell_id: string;
  status: "changed" | "unchanged";
  prior: { priority: string; change_score: number; confidence: number; summary: string };
  current: { priority: string; change_score: number; confidence: number; summary: string };
  changes: string[];
};

export type ReplayComparison = {
  mode: "additive";
  source_replay_id: string;
  prior_scoring_basis: string;
  current_scoring_basis: string;
  prior_alert_count: number;
  current_alert_count: number;
  changed_count: number;
  unchanged_count: number;
  rows: ReplayComparisonRow[];
  note: string;
};
