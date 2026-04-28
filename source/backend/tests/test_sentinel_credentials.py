from __future__ import annotations

from core import config as orbit_config


_SENTINEL_ENV_KEYS = (
    "SENTINEL_CLIENT_ID",
    "SENTINEL_CLIENT_SECRET",
    "SENTINEL_HUB_CLIENT_ID",
    "SENTINEL_HUB_CLIENT_SECRET",
    "SH_CLIENT_ID",
    "SH_CLIENT_SECRET",
    "SENTINEL_INSTANCE_ID",
    "SENTINEL_HUB_INSTANCE_ID",
    "SH_INSTANCE_ID",
    "SH_API_KEY",
)


def _clear_sentinel_env(monkeypatch) -> None:
    for key in _SENTINEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_resolve_sentinel_credentials_reads_sh_file_env_style(tmp_path, monkeypatch):
    _clear_sentinel_env(monkeypatch)
    secrets_path = tmp_path / "sh.txt"
    secrets_path.write_text(
        "SH_CLIENT_ID=client-from-sh\nSH_CLIENT_SECRET=secret-from-sh\n",
        encoding="utf-8",
    )

    creds = orbit_config.resolve_sentinel_credentials(secrets_path)

    assert creds.available
    assert creds.source == "file"
    assert creds.client_id == "client-from-sh"
    assert creds.client_secret == "secret-from-sh"
    assert creds.instance_id == ""


def test_resolve_sentinel_credentials_reads_three_line_trial_bundle(tmp_path, monkeypatch):
    _clear_sentinel_env(monkeypatch)
    secrets_path = tmp_path / "sh.txt"
    secrets_path.write_text(
        "instance-api-key\nsecret-oauth-key\nclient-user-key\n",
        encoding="utf-8",
    )

    creds = orbit_config.resolve_sentinel_credentials(secrets_path)

    assert creds.available
    assert creds.source == "file"
    assert creds.instance_id == "instance-api-key"
    assert creds.client_secret == "secret-oauth-key"
    assert creds.client_id == "client-user-key"


def test_resolve_sentinel_credentials_reads_labeled_trial_bundle(tmp_path, monkeypatch):
    _clear_sentinel_env(monkeypatch)
    secrets_path = tmp_path / "sh.txt"
    secrets_path.write_text(
        "API instance-api-key\nCLIENTID client-user-key\nCLIENT secret-oauth-key\n",
        encoding="utf-8",
    )

    creds = orbit_config.resolve_sentinel_credentials(secrets_path)

    assert creds.available
    assert creds.source == "file"
    assert creds.instance_id == "instance-api-key"
    assert creds.client_id == "client-user-key"
    assert creds.client_secret == "secret-oauth-key"


def test_resolve_sentinel_credentials_labeled_trial_bundle_ignores_later_user_label(tmp_path, monkeypatch):
    _clear_sentinel_env(monkeypatch)
    secrets_path = tmp_path / "sh.txt"
    secrets_path.write_text(
        "API instance-api-key\n"
        "CLIENTID client-user-key\n"
        "CLIENT secret-oauth-key\n"
        "USER portal-user-not-oauth-client\n",
        encoding="utf-8",
    )

    creds = orbit_config.resolve_sentinel_credentials(secrets_path)

    assert creds.available
    assert creds.client_id == "client-user-key"
    assert creds.client_secret == "secret-oauth-key"
    assert creds.instance_id == "instance-api-key"


def test_resolve_sentinel_credentials_reads_legacy_secret_then_id_lines(tmp_path, monkeypatch):
    _clear_sentinel_env(monkeypatch)
    secrets_path = tmp_path / "sentinel.txt"
    secrets_path.write_text("secret-line\nclient-line\n", encoding="utf-8")

    creds = orbit_config.resolve_sentinel_credentials(secrets_path)

    assert creds.available
    assert creds.client_id == "client-line"
    assert creds.client_secret == "secret-line"
    assert creds.instance_id == ""


def test_resolve_sentinel_credentials_prefers_env_over_files(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_CLIENT_ID", "client-from-env")
    monkeypatch.setenv("SH_CLIENT_SECRET", "secret-from-env")
    monkeypatch.setenv("SH_INSTANCE_ID", "instance-from-env")
    secrets_path = tmp_path / "sh.txt"
    secrets_path.write_text(
        "SH_CLIENT_ID=client-from-file\nSH_CLIENT_SECRET=secret-from-file\n",
        encoding="utf-8",
    )

    creds = orbit_config.resolve_sentinel_credentials(secrets_path)

    assert creds.source == "env"
    assert creds.client_id == "client-from-env"
    assert creds.client_secret == "secret-from-env"
    assert creds.instance_id == "instance-from-env"


def test_resolve_sentinel_credentials_falls_back_to_sh_file(tmp_path, monkeypatch):
    _clear_sentinel_env(monkeypatch)
    sh_path = tmp_path / "sh.txt"
    sh_path.write_text(
        "SENTINEL_CLIENT_ID=client-from-sh\nSENTINEL_CLIENT_SECRET=secret-from-sh\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        orbit_config,
        "_SENTINEL_SECRETS_FILE_PATHS",
        (tmp_path / "sentinel.txt", sh_path),
    )

    creds = orbit_config.resolve_sentinel_credentials()

    assert creds.available
    assert creds.client_id == "client-from-sh"
    assert creds.client_secret == "secret-from-sh"


def test_resolve_sentinel_credentials_returns_unavailable_for_empty_file(tmp_path, monkeypatch):
    _clear_sentinel_env(monkeypatch)
    secrets_path = tmp_path / "sh.txt"
    secrets_path.write_text("", encoding="utf-8")

    creds = orbit_config.resolve_sentinel_credentials(secrets_path)

    assert not creds.available
    assert creds.source == "unavailable"
