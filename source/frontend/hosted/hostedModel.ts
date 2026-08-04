export type HostedModelManifest = {
  schemaVersion: 1;
  kind: "browser-gguf";
  repo: string;
  file: string;
  revision: string;
  url: string;
  rawUrl: string;
  sha256: string;
  bytes: number;
  license: string;
  label: string;
  sizeLabel: string;
  capabilities: {
    textReasoning: true;
    imageInput: false;
    mmproj: null;
  };
};

export const MODEL_MANIFEST_PATH = `${import.meta.env.BASE_URL}model-manifest.json`;
const MAX_BROWSER_MODEL_BYTES = 512_000_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

function requiredText(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`Hosted model manifest field ${field} is invalid.`);
  return value.trim();
}

function resolveUrl(repo: string, revision: string, file: string, kind: "resolve" | "raw"): string {
  const encodedRepo = repo.split("/").map((part) => encodeURIComponent(part)).join("/");
  const encodedFile = file.split("/").map((part) => encodeURIComponent(part)).join("/");
  return `https://huggingface.co/${encodedRepo}/${kind}/${revision}/${encodedFile}`;
}

export function validateHostedModelManifest(value: unknown): HostedModelManifest {
  if (!isRecord(value) || value.schemaVersion !== 1 || value.kind !== "browser-gguf") {
    throw new Error("Hosted model manifest must use schema version 1 and browser-gguf kind.");
  }
  const repo = requiredText(value.repo, "repo");
  const file = requiredText(value.file, "file");
  const revision = requiredText(value.revision, "revision");
  const sha256 = requiredText(value.sha256, "sha256").toLowerCase();
  const bytes = value.bytes;
  const capabilities = value.capabilities;
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo) || file.includes("..") || file.startsWith("/") || !/^[a-z0-9._/-]+\.gguf$/i.test(file) || !/^[a-f0-9]{40}$/.test(revision) || !/^[a-f0-9]{64}$/.test(sha256)) {
    throw new Error("Hosted model manifest must use a pinned revision, SHA-256, and GGUF file.");
  }
  if (typeof bytes !== "number" || !Number.isSafeInteger(bytes) || bytes <= 0 || bytes > MAX_BROWSER_MODEL_BYTES) {
    throw new Error("Hosted model manifest bytes must be a positive integer within the browser safety limit.");
  }
  if (!isRecord(capabilities) || capabilities.textReasoning !== true || capabilities.imageInput !== false || capabilities.mmproj !== null) {
    throw new Error("Hosted model capabilities must explicitly describe the text-only browser contract.");
  }
  const url = requiredText(value.url, "url");
  const rawUrl = requiredText(value.rawUrl, "rawUrl");
  if (url !== resolveUrl(repo, revision, file, "resolve") || rawUrl !== resolveUrl(repo, revision, file, "raw")) {
    throw new Error("Hosted model manifest URLs do not match the pinned repository inventory.");
  }
  if (!url.startsWith("https://huggingface.co/") || !rawUrl.startsWith("https://huggingface.co/") || !requiredText(value.license, "license")) {
    throw new Error("Hosted model manifest must use public HTTPS Hugging Face URLs and disclose a license.");
  }
  return {
    schemaVersion: 1,
    kind: "browser-gguf",
    repo,
    file,
    revision,
    url,
    rawUrl,
    sha256,
    bytes,
    license: requiredText(value.license, "license"),
    label: requiredText(value.label, "label"),
    sizeLabel: requiredText(value.sizeLabel, "sizeLabel"),
    capabilities: { textReasoning: true, imageInput: false, mmproj: null },
  };
}

export async function loadHostedModelManifest(signal?: AbortSignal): Promise<HostedModelManifest> {
  const response = await fetch(MODEL_MANIFEST_PATH, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new Error(`Hosted model manifest could not be loaded (HTTP ${response.status}).`);
  return validateHostedModelManifest(await response.json());
}

export async function verifyHostedModelArtifact(manifest: HostedModelManifest, signal?: AbortSignal): Promise<void> {
  const pointerResponse = await fetch(manifest.rawUrl, { cache: "no-store", signal });
  if (!pointerResponse.ok) throw new Error(`Hosted model pointer could not be read (HTTP ${pointerResponse.status}).`);
  const pointer = await pointerResponse.text();
  const pointerHash = pointer.match(/^oid sha256:([a-f0-9]{64})$/m)?.[1];
  if (pointerHash !== manifest.sha256) throw new Error("Hosted model SHA-256 does not match the sealed manifest.");

  const headResponse = await fetch(manifest.url, { method: "HEAD", cache: "no-store", signal });
  if (!headResponse.ok) throw new Error(`Hosted model inventory could not be read (HTTP ${headResponse.status}).`);
  const contentLength = Number(headResponse.headers.get("content-length"));
  if (!Number.isSafeInteger(contentLength) || contentLength !== manifest.bytes) {
    throw new Error("Hosted model byte count does not match the sealed manifest.");
  }
}
