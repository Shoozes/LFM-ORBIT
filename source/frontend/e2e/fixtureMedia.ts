import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SEEDED_DATA_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "backend",
  "assets",
  "seeded_data",
);

export function readSeededTimelapseDataUrl(fileName = "nasa_aa01bc81.webm") {
  const videoPath = path.join(SEEDED_DATA_ROOT, fileName);
  return `data:video/webm;base64,${readFileSync(videoPath).toString("base64")}`;
}
