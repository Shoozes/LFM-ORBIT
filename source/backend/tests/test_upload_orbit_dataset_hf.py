from __future__ import annotations

import json
import subprocess

from scripts import upload_orbit_dataset_hf


def test_resolve_hf_token_reads_first_non_comment_line(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    token_path = tmp_path / "hf.txt"
    token_path.write_text("\n# local token\nhf_local_token\n", encoding="utf-8")

    token, source = upload_orbit_dataset_hf.resolve_hf_token(token_path)

    assert token == "hf_local_token"
    assert source == "file"


def test_resolve_hf_token_prefers_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_env_token")
    token_path = tmp_path / "hf.txt"
    token_path.write_text("hf_file_token\n", encoding="utf-8")

    token, source = upload_orbit_dataset_hf.resolve_hf_token(token_path)

    assert token == "hf_env_token"
    assert source == "env"


def test_build_upload_command_omits_token(tmp_path):
    command = upload_orbit_dataset_hf.build_upload_command(
        repo_id="user/orbit-data",
        dataset_dir=tmp_path,
        revision="main",
        commit_message="Update dataset",
        create_pr=True,
        delete_patterns=["samples/**", "manifest.json"],
    )

    assert command[:3] == ["hf", "upload", "user/orbit-data"]
    assert "--type" in command
    assert "dataset" in command
    assert "--commit-message" in command
    assert "Update dataset" in command
    assert "--create-pr" in command
    assert command[-4:] == ["--delete", "samples/**", "--delete", "manifest.json"]
    assert all("hf_" not in item for item in command)


def test_build_repo_create_command_private():
    command = upload_orbit_dataset_hf.build_repo_create_command(
        repo_id="user/orbit-data",
        private=True,
    )

    assert command == [
        "hf",
        "repos",
        "create",
        "user/orbit-data",
        "--type",
        "dataset",
        "--exist-ok",
        "--private",
    ]


def test_run_hf_command_reports_cli_failure_without_token(monkeypatch, capsys):
    def fake_run(command, *, env, check):
        assert env["HF_TOKEN"] == "hf_secret_token"
        assert check is True
        raise subprocess.CalledProcessError(403, command)

    monkeypatch.setattr(upload_orbit_dataset_hf.subprocess, "run", fake_run)

    code = upload_orbit_dataset_hf.run_hf_command(
        ["hf", "repos", "create", "user/orbit-data", "--type", "dataset"],
        env={"HF_TOKEN": "hf_secret_token"},
    )

    output = capsys.readouterr().out
    assert code == 403
    assert "exit code 403" in output
    assert "dataset write/create permission" in output
    assert "hf_secret_token" not in output


def test_validate_dataset_dir_accepts_packaged_retag_output(tmp_path):
    dataset = tmp_path / "retagged"
    images = dataset / "images"
    images.mkdir(parents=True)
    (images / "asset.png").write_bytes(b"png")
    (dataset / "training_assets.jsonl").write_text(
        json.dumps({"asset_id": "a1", "image": "images/asset.png"}) + "\n",
        encoding="utf-8",
    )
    (dataset / "metadata.jsonl").write_text(
        json.dumps({"asset_id": "a1", "file_name": "images/asset.png"}) + "\n",
        encoding="utf-8",
    )
    (dataset / "README.md").write_text(
        "---\n"
        "configs:\n"
        "- config_name: default\n"
        "  data_files:\n"
        "  - split: train\n"
        "    path: training_assets.jsonl\n"
        "---\n",
        encoding="utf-8",
    )

    assert upload_orbit_dataset_hf.validate_dataset_dir(dataset) == []


def test_validate_dataset_dir_blocks_path_leaks_missing_assets_and_empty_configs(tmp_path):
    dataset = tmp_path / "retagged"
    dataset.mkdir()
    (dataset / "training_assets.jsonl").write_text(
        json.dumps({
            "asset_id": "a1",
            "image": "images/missing.png",
            "metadata": {
                "references": [
                    {"video_source": r"C:\Users\dev\repo\runtime-data\modeling\orbit-export\samples\a\timelapse.webm"}
                ]
            },
        })
        + "\n",
        encoding="utf-8",
    )
    (dataset / "mission_metadata.jsonl").write_text("", encoding="utf-8")
    (dataset / "README.md").write_text(
        "---\n"
        "configs:\n"
        "- config_name: default\n"
        "  data_files:\n"
        "  - split: train\n"
        "    path: training_assets.jsonl\n"
        "- config_name: mission_metadata\n"
        "  data_files:\n"
        "  - split: train\n"
        "    path: mission_metadata.jsonl\n"
        "---\n",
        encoding="utf-8",
    )

    issues = upload_orbit_dataset_hf.validate_dataset_dir(dataset)

    assert "training_assets.jsonl contains a local absolute path" in issues
    assert "training_assets.jsonl references missing asset: images/missing.png" in issues
    assert "README.md config references empty JSONL file: mission_metadata.jsonl" in issues
