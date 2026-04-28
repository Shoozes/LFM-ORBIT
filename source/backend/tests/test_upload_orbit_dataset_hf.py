from __future__ import annotations

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
    )

    assert command[:3] == ["hf", "upload", "user/orbit-data"]
    assert "--type" in command
    assert "dataset" in command
    assert "--commit-message" in command
    assert "Update dataset" in command
    assert "--create-pr" in command
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
