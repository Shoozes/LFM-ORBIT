export type Mission = {
  id: number;
  task_text: string;
  bbox: number[] | null;
  start_date: string | null;
  end_date: string | null;
  status: "active" | "idle" | "complete";
  mission_mode?: "live" | "replay";
  confirmation_policy?: "single_acquisition" | "distinct_acquisition" | null;
  replay_id?: string | null;
  summary?: string | null;
  use_case_id?: string | null;
  target_pack_id?: string | null;
  object_targets?: ObjectTarget[];
  use_case_confidence?: number | null;
  use_case_decision?: Record<string, unknown> | null;
  cells_scanned: number;
  flags_found: number;
  created_at: string;
};

export type ObjectTarget = {
  label: string;
  prompt: string;
  class_key: string;
  enabled: boolean;
};

export type TargetPack = {
  id: string;
  name: string;
  description: string;
  targets: ObjectTarget[];
};
