import { resolveHostedModelEnabled } from "./hostedConfigCore.js";

const isHostedBuild = ["hosted", "pages"].includes(import.meta.env.MODE) || import.meta.env.VITE_ORBIT_BUILD === "hosted";
const modelEnabled = resolveHostedModelEnabled(import.meta.env.MODE, import.meta.env.VITE_HOSTED_MODEL_ENABLED);

export const HOSTED_DEPLOYMENT = Object.freeze({
  isHostedBuild,
  mode: import.meta.env.MODE,
  modelEnabled,
  route: isHostedBuild ? import.meta.env.BASE_URL : "/hosted",
});
export const IS_HOSTED_BUILD = HOSTED_DEPLOYMENT.isHostedBuild;
export const HOSTED_ROUTE = HOSTED_DEPLOYMENT.route;
export const HOSTED_MODEL_ENABLED = HOSTED_DEPLOYMENT.modelEnabled;

const RELATIVE_ASSET_PATTERN = /^[A-Za-z0-9._/-]+$/;

export function resolveHostedAsset(relativePath: string): string {
  const normalizedPath = relativePath.trim().replace(/^\/+/, "");
  if (!normalizedPath || normalizedPath.includes("..") || normalizedPath.includes("\\") || !RELATIVE_ASSET_PATTERN.test(normalizedPath)) {
    throw new Error("Hosted assets must use safe, repo-relative paths.");
  }
  return `${import.meta.env.BASE_URL}${normalizedPath}`;
}
