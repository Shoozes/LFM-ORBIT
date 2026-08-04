export const IS_HOSTED_BUILD = ["hosted", "pages"].includes(import.meta.env.MODE) || import.meta.env.VITE_ORBIT_BUILD === "hosted";
export const HOSTED_ROUTE = IS_HOSTED_BUILD ? import.meta.env.BASE_URL : "/hosted";

const RELATIVE_ASSET_PATTERN = /^[A-Za-z0-9._/-]+$/;

export function resolveHostedAsset(relativePath: string): string {
  const normalizedPath = relativePath.trim().replace(/^\/+/, "");
  if (!normalizedPath || normalizedPath.includes("..") || normalizedPath.includes("\\") || !RELATIVE_ASSET_PATTERN.test(normalizedPath)) {
    throw new Error("Hosted assets must use safe, repo-relative paths.");
  }
  return `${import.meta.env.BASE_URL}${normalizedPath}`;
}
