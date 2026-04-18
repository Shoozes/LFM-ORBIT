export type Mission = {
  id: number;
  task_text: string;
  bbox: number[] | null;
  start_date: string | null;
  end_date: string | null;
  status: "active" | "idle" | "complete";
  cells_scanned: number;
  flags_found: number;
  created_at: string;
};
