export type MapCameraRequest = {
  id: string;
  label: string;
  center: [number, number];
  bbox?: number[] | null;
  zoom?: number;
  pitch?: number;
  bearing?: number;
  reason?: string | null;
  source?: string | null;
  locationType?: string | null;
  terrainContext?: string | null;
  missionContext?: string | null;
  semanticTags?: string[];
  suggestedTargets?: string[];
  evidenceGuidance?: string | null;
};
