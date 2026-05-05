export type VlmBox = {
  label: string;
  bbox: number[];
  bbox_format?: "unit_yxyx" | "unit_xyxy";
  confidence?: number;
  color_key?: string;
  source_model?: string;
  prompt?: string;
  runtime_truth_mode?: string;
  imagery_origin?: string;
  scoring_basis?: string;
};
