from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_ci_workflow_runs_on_main_and_exposes_required_summary_check():
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "  push:" in workflow
    assert "      - main" in workflow
    assert "  pull_request:" in workflow
    assert "  ci-summary:" in workflow
    assert "    name: ci-summary" in workflow
    assert "    if: always()" in workflow
    assert "needs.security-static.result" in workflow
    assert "--no-emit-project" in workflow


def test_github_workflows_use_node24_native_action_majors():
    ci_workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    codeql_workflow = (REPO_ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")

    for action in (
        "actions/checkout@v7",
        "actions/setup-node@v7",
        "actions/setup-python@v7",
        "astral-sh/setup-uv@v8.3.2",
        "actions/upload-artifact@v7",
        "gitleaks/gitleaks-action@v3",
    ):
        assert action in ci_workflow

    for deprecated_action in (
        "actions/checkout@v4",
        "actions/setup-node@v4",
        "actions/setup-python@v5",
        "astral-sh/setup-uv@v5",
        "actions/upload-artifact@v4",
        "gitleaks/gitleaks-action@v2",
    ):
        assert deprecated_action not in ci_workflow

    assert "actions/checkout@v7" in codeql_workflow
    assert "github/codeql-action/init@v4" in codeql_workflow
    assert "github/codeql-action/autobuild@v4" in codeql_workflow
    assert "github/codeql-action/analyze@v4" in codeql_workflow


def test_pages_workflow_builds_and_deploys_only_the_hosted_project_path():
    workflow_path = REPO_ROOT / ".github/workflows/pages.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    assert "  push:" in workflow
    assert "      - main" in workflow
    assert "  workflow_dispatch:" in workflow
    assert "  pull_request:" not in workflow
    assert "  pages: write" in workflow
    assert "  id-token: write" in workflow
    assert "VITE_PUBLIC_BASE: \"/${{ github.event.repository.name }}/\"" in workflow
    assert "VITE_HOSTED_MODEL_ENABLED: \"false\"" in workflow
    assert "timeout-minutes: 20" in workflow
    assert "npx playwright install --with-deps chromium" in workflow
    assert "npm run build:pages" in workflow
    assert "npm run test:hosted:pages" in workflow
    assert workflow.index("npx playwright install --with-deps chromium") < workflow.index("npm run test:hosted:pages")
    assert "actions/configure-pages@v6" in workflow
    assert "actions/upload-pages-artifact@v5" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "path: source/frontend/dist-pages" in workflow
    assert "needs: build" in workflow
    assert "name: github-pages" in workflow
    assert "url: ${{ steps.deployment.outputs.page_url }}" in workflow
    assert "page_url: ${{ steps.deployment.outputs.page_url }}" in workflow
    assert "static-smoke:" in workflow
    assert "needs: deploy" in workflow
    assert "npm run test:hosted:pages:live:static" in workflow
    assert workflow.rfind("npx playwright install --with-deps chromium") < workflow.index("npm run test:hosted:pages:live:static")
    assert "actions/upload-artifact@v7" in workflow


def test_default_playwright_suite_excludes_pages_only_specs():
    config = (REPO_ROOT / "source/frontend/playwright.config.ts").read_text(encoding="utf-8")

    assert '"**/hosted.pages.spec.ts"' in config
    assert '"**/hosted.pages.live.spec.ts"' in config
    assert '"**/hosted.pages.live.static.spec.ts"' in config


def test_default_playwright_suite_excludes_media_production_specs():
    config = (REPO_ROOT / "source/frontend/playwright.config.ts").read_text(encoding="utf-8")
    media_config = (REPO_ROOT / "source/frontend/playwright.media.config.ts").read_text(encoding="utf-8")
    package_json = (REPO_ROOT / "source/frontend/package.json").read_text(encoding="utf-8")

    for spec in (
        '"**/capture_screenshots.spec.ts"',
        '"**/dual_agent_demo.spec.ts"',
        '"**/tutorial_video.spec.ts"',
    ):
        assert spec in config
        assert spec in media_config
    assert '"test:media":' in package_json
    assert '"demo:tutorial": "npm run test:media' in package_json
    assert '"demo:screenshots": "npm run test:media' in package_json


def test_ci_separates_hosted_smoke_application_e2e_and_fast_contracts():
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for marker in (
        "scope:",
        "docs_only:",
        "Classify changed paths",
        "workflow-contracts:",
        "hosted-smoke:",
        "app-e2e:",
        "name: hosted-smoke-artifacts",
        "name: app-e2e-artifacts",
        "ACTIONLINT_VERSION: v1.7.7",
        "name: dependency-audit-reports",
    ):
        assert marker in workflow
    assert "paths-ignore:" not in workflow
    assert "needs:\n      - scope\n      - frontend\n    if: needs.scope.outputs.docs_only != 'true'" in workflow
    assert "npm run verify:hosted" in workflow
    assert "npm run test:e2e" in workflow


def test_pages_smoke_uses_exact_navigation_locators():
    pages_spec = (REPO_ROOT / "source/frontend/e2e/hosted.pages.spec.ts").read_text(encoding="utf-8")

    assert 'getByRole("link", { name: "Saved evidence", exact: true })' in pages_spec
