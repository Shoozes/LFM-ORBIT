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
    assert "npm run build:pages" in workflow
    assert "npm run test:hosted:pages" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "path: source/frontend/dist-pages" in workflow
    assert "needs: build" in workflow
    assert "name: github-pages" in workflow
    assert "url: ${{ steps.deployment.outputs.page_url }}" in workflow


def test_default_playwright_suite_excludes_pages_only_specs():
    config = (REPO_ROOT / "source/frontend/playwright.config.ts").read_text(encoding="utf-8")

    assert '"**/hosted.pages.spec.ts"' in config
    assert '"**/hosted.pages.live.spec.ts"' in config
