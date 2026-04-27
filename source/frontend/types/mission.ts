export type Mission = {
  id: number;
  task_text: string;
  bbox: number[] | null;
  start_date: string | null;
  end_date: string | null;
  status: "active" | "idle" | "complete";
  mission_mode?: "live" | "replay";
  replay_id?: string | null;
  summary?: string | null;
  use_case_id?: string | null;
  use_case_confidence?: number | null;
  use_case_decision?: Record<string, unknown> | null;
  cells_scanned: number;
  flags_found: number;
  created_at: string;
};
