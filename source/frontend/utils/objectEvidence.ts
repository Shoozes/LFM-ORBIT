import type { VlmBox } from "../types/visualEvidence";

export const OBJECT_EVIDENCE_COLORS: Record<string, string> = {
  aid: "#38bdf8",
  cargo: "#f59e0b",
  construction: "#f97316",
  custom: "#a3e635",
  cryosphere: "#67e8f9",
  environmental: "#2dd4bf",
  fallback: "#a1a1aa",
  hazard: "#fb7185",
  industrial_surface: "#d97706",
  infrastructure: "#c084fc",
  land_cover_change: "#22c55e",
  lifeline: "#22d3ee",
  mobility: "#facc15",
  surface_change: "#f59e0b",
  structure: "#34d399",
  urban_surface: "#64748b",
  vehicle: "#f97316",
  vegetation: "#84cc16",
  vessel: "#38bdf8",
  water: "#60a5fa",
  water_industrial: "#0ea5e9",
  waterline: "#2dd4bf",
};

export function clampUnit(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function colorForVlmBox(box: VlmBox): string {
  const key = (box.color_key ?? "").trim().toLowerCase();
  if (key && OBJECT_EVIDENCE_COLORS[key]) return OBJECT_EVIDENCE_COLORS[key];
  const label = box.label.toLowerCase();
  if (/(smoke|burn|scar|flare|hazard|fire)/.test(label)) return OBJECT_EVIDENCE_COLORS.hazard;
  if (/(road|bridge|lifeline|queue)/.test(label)) return OBJECT_EVIDENCE_COLORS.lifeline;
  if (/(clearing|canopy|forest|vegetation)/.test(label)) return OBJECT_EVIDENCE_COLORS.land_cover_change;
  if (/(soil|bare|surface)/.test(label)) return OBJECT_EVIDENCE_COLORS.surface_change;
  if (/(ship|vessel|boat)/.test(label)) return OBJECT_EVIDENCE_COLORS.vessel;
  if (/(truck|vehicle)/.test(label)) return OBJECT_EVIDENCE_COLORS.vehicle;
  if (/(debris|slick|foam|river)/.test(label)) return OBJECT_EVIDENCE_COLORS.environmental;
  if (/(building|home|shelter|tent|roof)/.test(label)) return OBJECT_EVIDENCE_COLORS.structure;
  return OBJECT_EVIDENCE_COLORS.custom;
}

export function isMaritimeActivityLabel(label: string): boolean {
  return /(ship|ships|vessel|vessels|boat|boats|barge|barges|maritime|anchorage|queue)/i.test(label);
}

export function shouldUseAreaEvidenceLanguage(boxOrSummary?: {
  label?: string;
  scoring_basis?: string;
  imagery_origin?: string;
  confidence?: number;
  count_quality?: string;
} | null): boolean {
  if (!boxOrSummary) return false;
  const label = String(boxOrSummary.label ?? "");
  if (!isMaritimeActivityLabel(label)) return false;
  const scoringBasis = String(boxOrSummary.scoring_basis ?? "").toLowerCase();
  const imageryOrigin = String(boxOrSummary.imagery_origin ?? "").toLowerCase();
  const countQuality = String(boxOrSummary.count_quality ?? "").toLowerCase();
  const confidence = typeof boxOrSummary.confidence === "number" ? boxOrSummary.confidence : 1;
  return (
    scoringBasis === "visual_only" ||
    imageryOrigin === "cached_api" ||
    countQuality === "activity_region" ||
    confidence < 0.86
  );
}

export function shouldUseRegionEvidenceLanguage(boxOrSummary?: {
  label?: string;
  count_quality?: string;
} | null): boolean {
  if (!boxOrSummary) return false;
  const label = String(boxOrSummary.label ?? "").toLowerCase();
  const countQuality = String(boxOrSummary.count_quality ?? "").toLowerCase();
  return (
    ["region", "corridor", "area", "activity_region"].includes(countQuality) ||
    /(region|boundary|corridor|clearing candidate|debris candidate|slick candidate|activity cluster)/.test(label)
  );
}

export function displayObjectEvidenceLabel(boxOrLabel: VlmBox | string): string {
  const box = typeof boxOrLabel === "string" ? { label: boxOrLabel } : boxOrLabel;
  if (shouldUseAreaEvidenceLanguage(box)) return "maritime activity";
  return String(box.label || "object");
}

export function displayObjectEvidenceCount(label: string, count: number, sampleBox?: VlmBox): string {
  if (shouldUseAreaEvidenceLanguage(sampleBox ?? { label, scoring_basis: "visual_only" })) {
    return count > 1 ? `${count} activity areas` : "area-level";
  }
  if (shouldUseRegionEvidenceLanguage(sampleBox ?? { label })) {
    return count > 1 ? `${count} regions` : "region-level";
  }
  return String(count);
}

export function objectEvidenceScopeNote(boxOrLabel: VlmBox | string): string {
  const box = typeof boxOrLabel === "string" ? { label: boxOrLabel } : boxOrLabel;
  if (shouldUseAreaEvidenceLanguage(box)) {
    return "Area-level evidence: do not treat this as an exact object count.";
  }
  if (shouldUseRegionEvidenceLanguage(box)) {
    return "Region-level candidate: use as review evidence, not an exact object count.";
  }
  return "Object-level candidate: still requires source and model provenance review.";
}

export function bboxToUnitYxyx(box: VlmBox): [number, number, number, number] {
  const [a = 0, b = 0, c = 0, d = 0] = box.bbox;
  if (box.bbox_format === "unit_xyxy") {
    const xmin = clampUnit(a);
    const ymin = clampUnit(b);
    const xmax = clampUnit(c);
    const ymax = clampUnit(d);
    return [
      Math.min(ymin, ymax),
      Math.min(xmin, xmax),
      Math.max(ymin, ymax),
      Math.max(xmin, xmax),
    ];
  }
  const ymin = clampUnit(a);
  const xmin = clampUnit(b);
  const ymax = clampUnit(c);
  const xmax = clampUnit(d);
  return [
    Math.min(ymin, ymax),
    Math.min(xmin, xmax),
    Math.max(ymin, ymax),
    Math.max(xmin, xmax),
  ];
}

export function unitBoxToGeographicBbox(
  activeBbox: number[],
  box: VlmBox,
): [number, number, number, number] {
  const [west, south, east, north] = activeBbox;
  const [ymin, xmin, ymax, xmax] = bboxToUnitYxyx(box);
  const boxNorth = north - (north - south) * ymin;
  const boxSouth = north - (north - south) * ymax;
  const boxWest = west + (east - west) * xmin;
  const boxEast = west + (east - west) * xmax;
  return [boxWest, boxSouth, boxEast, boxNorth];
}
