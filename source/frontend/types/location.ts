export type LocationBbox = [number, number, number, number];

export type LocationPreviewTile = {
  z: number;
  x: number;
  y: number;
  url: string;
};

export type LocationCandidate = {
  id: string;
  query: string;
  label: string;
  provider: string;
  featureType: string;
  center: [number, number];
  bbox: LocationBbox;
  confidence: number;
  reason: string;
  previewTiles: LocationPreviewTile[];
};
