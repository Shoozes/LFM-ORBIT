#!/usr/bin/env python3
"""Fast text-level contracts for the repository's GitHub Actions topology."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} is missing: {needle}")


def main() -> int:
    ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    pages = (REPO_ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    playwright = (REPO_ROOT / "source/frontend/playwright.config.ts").read_text(encoding="utf-8")
    package_json = (REPO_ROOT / "source/frontend/package.json").read_text(encoding="utf-8")
    pages_spec = (REPO_ROOT / "source/frontend/e2e/hosted.pages.spec.ts").read_text(encoding="utf-8")

    for needle in (
        "scope:",
        "docs_only:",
        "Classify changed paths",
        "workflow-contracts:",
        "hosted-smoke:",
        "app-e2e:",
        "name: hosted-smoke-artifacts",
        "name: app-e2e-artifacts",
        "needs.workflow-contracts.result",
        "needs.hosted-smoke.result",
        "needs.app-e2e.result",
        "go install \"github.com/rhysd/actionlint/cmd/actionlint@${ACTIONLINT_VERSION}\"",
        "ACTIONLINT_VERSION: v1.7.7",
    ):
        _require(ci, needle, "CI workflow contract")

    if "paths-ignore:" in ci:
        raise AssertionError("CI should use the scope job so required ci-summary is never omitted")

    for media_spec in (
        "**/capture_screenshots.spec.ts",
        "**/dual_agent_demo.spec.ts",
        "**/tutorial_video.spec.ts",
    ):
        _require(playwright, media_spec, "Playwright media exclusion")
    _require(playwright, '"**/hosted.pages.live.static.spec.ts"', "Pages release exclusion")

    _require(package_json, '"test:media":', "media test command")
    _require(package_json, '"demo:tutorial": "npm run test:media', "tutorial media command")
    _require(package_json, '"demo:screenshots": "npm run test:media', "screenshot media command")
    _require(pages_spec, 'getByRole("link", { name: "Saved evidence", exact: true })', "Pages navigation locator")

    for needle in (
        "pages: write",
        "id-token: write",
        "VITE_HOSTED_MODEL_ENABLED: \"false\"",
        "path: source/frontend/dist-pages",
        "needs: deploy",
    ):
        _require(pages, needle, "Pages workflow contract")

    print("Workflow contracts passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
