const VALID_MODEL_FLAGS = new Set(["true", "false"]);

/**
 * Resolve the browser-model policy once at the build boundary.
 * Pages is fail-closed; local/hosted builds remain enabled by default so the
 * opt-in browser model lane keeps its existing developer ergonomics.
 */
export function resolveHostedModelEnabled(mode, rawValue) {
  const value = typeof rawValue === "string" ? rawValue.trim().toLowerCase() : "";
  if (value && !VALID_MODEL_FLAGS.has(value)) {
    throw new Error("VITE_HOSTED_MODEL_ENABLED must be exactly true or false when provided.");
  }
  if (mode === "pages") return value === "true";
  return value !== "false";
}
