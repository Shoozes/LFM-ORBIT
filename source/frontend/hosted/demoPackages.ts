export type DemoPackage = {
  id: string;
  title: string;
  location: string;
  summary: string;
  signal: string;
  teachingPoint: string;
  facts: string[];
  evidence: DemoPackageEvidence;
  imageSrc?: string;
  imageAlt?: string;
};

export type DemoPackageEvidence = {
  bbox: [number, number, number, number];
  imageryOrigin: "cached_api";
  observationWindow: { start: string; end: string };
  retentionDecision: "candidate" | "review" | "abstain";
  reviewSummary: string;
  runtimeTruthMode: "replay";
  scoringBasis: string;
  sourceAsset: string;
  sourceReplayId: string;
};

export type DemoPackageIndex = {
  schemaVersion: 2;
  packages: DemoPackage[];
};

export const DEMO_PACKAGE_MANIFEST_PATH = `${import.meta.env.BASE_URL}demo-packages/index.json`;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

function requiredText(value: unknown, field: string, maxLength = 600): string {
  if (typeof value !== "string" || !value.trim() || value.trim().length > maxLength) {
    throw new Error(`Hosted package manifest field ${field} must be a non-empty string.`);
  }
  return value.trim();
}

function validatePackage(value: unknown, index: number): DemoPackage {
  if (!isRecord(value)) throw new Error(`Hosted package ${index + 1} must be an object.`);
  const imageSrc = value.imageSrc === undefined ? undefined : requiredText(value.imageSrc, `packages[${index}].imageSrc`, 180);
  const imageAlt = value.imageAlt === undefined ? undefined : requiredText(value.imageAlt, `packages[${index}].imageAlt`, 240);
  if (imageSrc && (!/^\/demo-assets\/[a-z0-9._/-]+$/i.test(imageSrc) || imageSrc.includes("..") || !imageAlt)) {
    throw new Error(`Hosted package ${index + 1} must use a repo-local image and accessible alt text.`);
  }
  if (!Array.isArray(value.facts) || value.facts.length === 0 || value.facts.length > 8 || value.facts.some((fact) => typeof fact !== "string" || !fact.trim() || fact.trim().length > 300)) {
    throw new Error(`Hosted package ${index + 1} must include non-empty facts.`);
  }
  const evidence = value.evidence;
  if (!isRecord(evidence)) throw new Error(`Hosted package ${index + 1} must include evidence provenance.`);
  const rawBbox = evidence.bbox;
  if (!Array.isArray(rawBbox) || rawBbox.length !== 4 || rawBbox.some((coordinate) => typeof coordinate !== "number" || !Number.isFinite(coordinate))) {
    throw new Error(`Hosted package ${index + 1} evidence bbox is invalid.`);
  }
  if (rawBbox[0] >= rawBbox[2] || rawBbox[1] >= rawBbox[3]) {
    throw new Error(`Hosted package ${index + 1} evidence bbox must be ordered.`);
  }
  const observationWindow = evidence.observationWindow;
  if (!isRecord(observationWindow)) throw new Error(`Hosted package ${index + 1} evidence window is invalid.`);
  const runtimeTruthMode = requiredText(evidence.runtimeTruthMode, `packages[${index}].evidence.runtimeTruthMode`, 40);
  const imageryOrigin = requiredText(evidence.imageryOrigin, `packages[${index}].evidence.imageryOrigin`, 40);
  const retentionDecision = requiredText(evidence.retentionDecision, `packages[${index}].evidence.retentionDecision`, 40);
  if (runtimeTruthMode !== "replay" || imageryOrigin !== "cached_api" || !["candidate", "review", "abstain"].includes(retentionDecision)) {
    throw new Error(`Hosted package ${index + 1} evidence provenance is outside the saved replay contract.`);
  }
  const sourceAsset = requiredText(evidence.sourceAsset, `packages[${index}].evidence.sourceAsset`, 240);
  const sourceReplayId = requiredText(evidence.sourceReplayId, `packages[${index}].evidence.sourceReplayId`, 100);
  if (!/^source\/backend\/assets\/replays\/[a-z0-9_]+\.json$/i.test(sourceAsset) || !/^[a-z0-9_]+$/.test(sourceReplayId)) {
    throw new Error(`Hosted package ${index + 1} evidence source must be a local replay manifest.`);
  }
  return {
    id: requiredText(value.id, `packages[${index}].id`, 80),
    title: requiredText(value.title, `packages[${index}].title`, 160),
    location: requiredText(value.location, `packages[${index}].location`, 180),
    summary: requiredText(value.summary, `packages[${index}].summary`, 700),
    signal: requiredText(value.signal, `packages[${index}].signal`, 220),
    teachingPoint: requiredText(value.teachingPoint, `packages[${index}].teachingPoint`, 500),
    facts: value.facts.map((fact) => String(fact).trim()),
    evidence: {
      bbox: rawBbox as [number, number, number, number],
      imageryOrigin: "cached_api",
      observationWindow: {
        end: requiredText(observationWindow.end, `packages[${index}].evidence.observationWindow.end`, 80),
        start: requiredText(observationWindow.start, `packages[${index}].evidence.observationWindow.start`, 80),
      },
      retentionDecision: retentionDecision as DemoPackageEvidence["retentionDecision"],
      reviewSummary: requiredText(evidence.reviewSummary, `packages[${index}].evidence.reviewSummary`, 700),
      runtimeTruthMode: "replay",
      scoringBasis: requiredText(evidence.scoringBasis, `packages[${index}].evidence.scoringBasis`, 120),
      sourceAsset,
      sourceReplayId,
    },
    ...(imageSrc ? { imageSrc, imageAlt } : {}),
  };
}

export function validateDemoPackageIndex(value: unknown): readonly DemoPackage[] {
  if (!isRecord(value) || value.schemaVersion !== 2 || !Array.isArray(value.packages) || value.packages.length === 0 || value.packages.length > 12) {
    throw new Error("Hosted package manifest must be schema version 2 with 1-12 packages.");
  }
  const packages = value.packages.map(validatePackage);
  const ids = new Set<string>();
  for (const item of packages) {
    if (ids.has(item.id)) throw new Error(`Hosted package id is duplicated: ${item.id}`);
    ids.add(item.id);
  }
  return packages;
}

export async function loadDemoPackages(signal?: AbortSignal): Promise<readonly DemoPackage[]> {
  const response = await fetch(DEMO_PACKAGE_MANIFEST_PATH, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new Error(`Hosted package manifest could not be loaded (HTTP ${response.status}).`);
  return validateDemoPackageIndex(await response.json());
}

export const SYSTEM_PROMPT = [
  "You are Orbit Classroom, a concise edge-AI tutor.",
  "The user is inspecting a saved demonstration package, not live satellite imagery.",
  "Explain evidence, uncertainty, browser inference, and downlink tradeoffs in plain language.",
  "Never claim that saved data is live, and say when the packet cannot support a conclusion.",
].join(" ");

export function packageContext(item: DemoPackage): string {
  return [
    `Package: ${item.title}`,
    `Location: ${item.location}`,
    `Signal: ${item.signal}`,
    `Facts: ${item.facts.join("; ")}`,
    `Evidence: ${item.evidence.runtimeTruthMode} / ${item.evidence.imageryOrigin} / ${item.evidence.scoringBasis}`,
    `Window: ${item.evidence.observationWindow.start} to ${item.evidence.observationWindow.end}`,
    `Review: ${item.evidence.reviewSummary}`,
  ].join("\n");
}
