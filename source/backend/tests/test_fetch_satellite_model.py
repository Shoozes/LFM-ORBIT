import json
import sys
from argparse import Namespace

from scripts import fetch_satellite_model


class _FakeResponse:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_download_file_streams_large_artifacts_to_disk(tmp_path, monkeypatch):
    response = _FakeResponse([b"orbit-", b"model", b"-bytes"])
    monkeypatch.setattr(fetch_satellite_model.urllib.request, "urlopen", lambda request: response)

    target_path = tmp_path / "artifact.gguf"
    fetch_satellite_model._download_file("https://example.test/model.gguf", target_path, token=None)

    assert target_path.read_bytes() == b"orbit-model-bytes"
    assert response.read_sizes == [
        fetch_satellite_model.DOWNLOAD_CHUNK_SIZE,
        fetch_satellite_model.DOWNLOAD_CHUNK_SIZE,
        fetch_satellite_model.DOWNLOAD_CHUNK_SIZE,
        fetch_satellite_model.DOWNLOAD_CHUNK_SIZE,
    ]


def test_copy_local_bundle_metadata_preserves_provenance_files(tmp_path):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    source_manifest_path = bundle_dir / "orbit_model_handoff.json"
    source_manifest_path.write_text(
        json.dumps(
            {
                "repo_id": "jc816/lfm-orbit-satellite",
                "training_result_manifest": "training_result_manifest.json",
            }
        ),
        encoding="utf-8",
    )
    (bundle_dir / "training_result_manifest.json").write_text("{\"run_id\": \"orbit-1\"}", encoding="utf-8")
    (bundle_dir / "README.md").write_text("# Orbit Bundle\n", encoding="utf-8")

    target_dir = tmp_path / "runtime-data" / "models" / "lfm2.5-vlm-450m"
    target_dir.mkdir(parents=True)

    copied = fetch_satellite_model._copy_local_bundle_metadata(
        source_manifest_path=source_manifest_path,
        handoff_payload=json.loads(source_manifest_path.read_text(encoding="utf-8")),
        training_result_manifest="training_result_manifest.json",
        target_dir=target_dir,
    )

    assert copied["source_handoff"] == target_dir / "source_handoff.json"
    assert copied["training_result_manifest"] == target_dir / "training_result_manifest.json"
    assert copied["readme"] == target_dir / "README.md"
    assert json.loads((target_dir / "source_handoff.json").read_text(encoding="utf-8"))["repo_id"] == "jc816/lfm-orbit-satellite"


def test_main_defaults_to_published_orbit_handoff_repo(tmp_path, monkeypatch, capsys):
    runtime_dir = tmp_path / "runtime-data"
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("LFM_MODEL_REPO_ID", raising=False)
    monkeypatch.delenv("CANOPY_SENTINEL_MODEL_REPO_ID", raising=False)
    monkeypatch.setattr(sys, "argv", ["fetch_satellite_model.py", "--dry-run"])

    handoff_payload = {
        "repo_id": "Shoozes/lfm2.5-450m-vl-orbit-satellite",
        "revision": "main",
        "model_subdir": "lfm2.5-vlm-450m",
        "model_filename": "LFM2.5-VL-450M-Q4_0.gguf",
        "base_model": "LiquidAI/LFM2.5-VL-450M",
        "quantization": "q4_0",
        "task": "orbit-satellite-triage",
        "training_result_manifest": "training_result_manifest.json",
    }
    monkeypatch.setattr(
        fetch_satellite_model,
        "_try_load_remote_handoff_manifest",
        lambda repo_id, revision, filename, token: handoff_payload,
    )

    exit_code = fetch_satellite_model.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Shoozes/lfm2.5-450m-vl-orbit-satellite@main" in output
    assert "LFM2.5-VL-450M-Q4_0.gguf" in output


def test_main_prefers_remote_handoff_manifest_and_preserves_repo_metadata(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime-data"
    monkeypatch.setenv("CANOPY_SENTINEL_RUNTIME_DIR", str(runtime_dir))

    handoff_payload = {
        "repo_id": "jc816/lfm-orbit-satellite",
        "revision": "release-2",
        "model_subdir": "remote-handoff",
        "model_filename": "remote-q4.gguf",
        "mmproj_filename": "remote-mmproj.gguf",
        "base_model": "LiquidAI/LFM2.5-VL-450M",
        "quantization": "Q4_0",
        "task": "deforestation-triage",
        "training_result_manifest": "training_result_manifest.json",
    }

    monkeypatch.setattr(
        fetch_satellite_model,
        "_parse_args",
        lambda: Namespace(
            source_manifest=None,
            handoff_manifest_filename="orbit_model_handoff.json",
            repo_id="jc816/lfm-orbit-satellite",
            revision="release-2",
            model_filename=None,
            mmproj_filename=None,
            model_subdir=None,
            base_model=None,
            quantization=None,
            task=None,
            token_env="HF_TOKEN",
            force=False,
            dry_run=False,
        ),
    )
    monkeypatch.setattr(
        fetch_satellite_model,
        "_try_load_remote_handoff_manifest",
        lambda repo_id, revision, filename, token: handoff_payload,
    )

    def _fake_download(url: str, target_path, token):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.name == "training_result_manifest.json":
            target_path.write_text("{\"run_id\": \"remote-orbit\"}", encoding="utf-8")
            return
        if target_path.name == "README.md":
            target_path.write_text("# Remote Bundle\n", encoding="utf-8")
            return
        target_path.write_bytes(b"gguf")

    monkeypatch.setattr(fetch_satellite_model, "_download_file", _fake_download)

    exit_code = fetch_satellite_model.main()

    target_dir = runtime_dir / "models" / "remote-handoff"
    assert exit_code == 0
    assert (target_dir / "remote-q4.gguf").exists()
    assert (target_dir / "remote-mmproj.gguf").exists()
    assert (target_dir / "source_handoff.json").exists()
    assert (target_dir / "training_result_manifest.json").exists()
    assert (target_dir / "README.md").exists()

    runtime_manifest = json.loads((target_dir / "model_manifest.json").read_text(encoding="utf-8"))
    assert runtime_manifest["repo_id"] == "jc816/lfm-orbit-satellite"
    assert runtime_manifest["revision"] == "release-2"
    assert runtime_manifest["model_filename"] == "remote-q4.gguf"
    assert runtime_manifest["mmproj_filename"] == "remote-mmproj.gguf"
    assert runtime_manifest["training_result_manifest"] == "training_result_manifest.json"
