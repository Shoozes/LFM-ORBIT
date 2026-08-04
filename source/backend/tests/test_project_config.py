from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_project_config_is_valid_and_points_to_main():
    config_path = REPO_ROOT / ".tools" / "project.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["name"] == "LFM-ORBIT"
    assert config["git"] == {
        "remote": "https://github.com/Shoozes/LFM-ORBIT.git",
        "trainingRemote": "https://github.com/Shoozes/GenUni.git",
        "defaultBranch": "main",
    }
    assert config["paths"] == {
        "secretsDir": ".tools/.secrets",
        "tokenFile": "gt.txt",
    }
    assert config["window"]["title"] == "LFM-ORBIT  //  Unified Controller"
    assert [group["label"] for group in config["groups"]] == [
        "AI Context Tools",
        "Run & Test",
        "Git",
    ]

    git_group = next(group for group in config["groups"] if group["label"] == "Git")
    push_button = next(button for button in git_group["buttons"] if button["label"] == "Push Reviewed Changes")
    assert "public LFM-ORBIT GitHub remote" in push_button["description"]
    assert "private GitHub repo" not in push_button["description"]


def test_project_config_does_not_unignore_secret_directory():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".tools/.secrets/" in gitignore
    assert "!.tools/project.json" in gitignore
    assert ".tools/.secrets/gt.txt" not in gitignore


def test_project_actions_reference_existing_targets_and_live_launcher_switches():
    config = json.loads((REPO_ROOT / ".tools" / "project.json").read_text(encoding="utf-8"))
    launcher = (REPO_ROOT / "run.ps1").read_text(encoding="utf-8")
    parameter_block = launcher.split("$ErrorActionPreference", 1)[0]
    supported_switches = {
        f"-{name}"
        for name in re.findall(r"\[switch\]\$(\w+)", parameter_block)
    }

    expected_run_labels = [
        "Install Full Runtime",
        "Start Web Dev",
        "Start Hosted Demo",
        "Clean Runtime State",
        "Verify Repo",
        "Install Dependencies Only",
    ]
    run_group = next(group for group in config["groups"] if group["label"] == "Run & Test")
    assert [button["label"] for button in run_group["buttons"]] == expected_run_labels

    for group in config["groups"]:
        for button in group["buttons"]:
            target = button.get("script") or button.get("path")
            assert target, f"Project action {button.get('label')} has no target"
            assert (REPO_ROOT / target).is_file(), f"Project action target is missing: {target}"

            if button.get("script") == "run.ps1":
                args = button.get("args", [])
                assert args, f"Launcher action has no arguments: {button['label']}"
                assert set(args) <= supported_switches, (
                    f"Launcher action uses unsupported switches: {button['label']}"
                )
                assert "-Task" not in args

    assert not any(
        stale in json.dumps(config)
        for stale in ("tauri", "sidecar", "bootstrap-runtime", "download-stack")
    )


def test_project_context_prompt_uses_a_live_default_summary_group():
    config = json.loads((REPO_ROOT / ".tools" / "project.json").read_text(encoding="utf-8"))
    bank = json.loads((REPO_ROOT / "summary_bank.json").read_text(encoding="utf-8"))

    context_tools = next(group for group in config["groups"] if group["label"] == "AI Context Tools")
    prompt_button = next(button for button in context_tools["buttons"] if button["label"] == "Print Context Group")
    prompt_group = prompt_button["prompt_arg"]["initial_value"]

    assert prompt_group in bank["groups"]
    assert prompt_group in bank["defaults"]["groups"]
    assert bank["groups"][prompt_group].get("_archived") is not True
