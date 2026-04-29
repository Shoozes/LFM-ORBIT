import numpy as np

from core import gallery


def test_load_cached_thumbnail_returns_png_data_url(monkeypatch, tmp_path):
    sig = "abc12345"
    webm_path = tmp_path / f"nasa_{sig}.webm"
    webm_path.write_bytes(b"stub")
    monkeypatch.setattr(gallery, "_SEEDED_DIR", tmp_path)
    monkeypatch.setattr(
        gallery.iio,
        "imiter",
        lambda *args, **kwargs: iter([np.zeros((32, 32, 3), dtype=np.uint8)]),
    )

    result = gallery._load_cached_thumbnail(sig, 24)

    assert result is not None
    assert result.startswith("data:image/png;base64,")


def test_fetch_thumbnail_prefers_cached_frame_when_esri_fails(monkeypatch):
    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(gallery.httpx, "Client", _FailingClient)
    monkeypatch.setattr(gallery, "_load_cached_thumbnail", lambda sig, size: "data:image/png;base64,cached")

    result = gallery._fetch_thumbnail(10.0, 20.0, size=32)

    assert result == "data:image/png;base64,cached"


def test_fetch_thumbnail_reports_cached_provenance_when_esri_fails(monkeypatch):
    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(gallery.httpx, "Client", _FailingClient)
    monkeypatch.setattr(gallery, "_load_cached_thumbnail", lambda sig, size: "data:image/png;base64,cached")

    result, source = gallery._fetch_thumbnail_with_provenance(10.0, 20.0, size=32)

    assert result == "data:image/png;base64,cached"
    assert source == "seeded_cache"


def test_fetch_thumbnail_falls_back_to_svg_when_cache_missing(monkeypatch):
    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(gallery.httpx, "Client", _FailingClient)
    monkeypatch.setattr(gallery, "_load_cached_thumbnail", lambda sig, size: None)

    result = gallery._fetch_thumbnail(10.0, 20.0, size=32)

    assert result is not None
    assert result.startswith("data:image/svg+xml;base64,")


def test_add_gallery_item_stores_evidence_provenance(monkeypatch, tmp_path):
    db_path = tmp_path / "agent_bus.sqlite"
    monkeypatch.setenv("AGENT_BUS_PATH", str(db_path))

    gallery.init_gallery(reset=True)
    gallery.add_gallery_item(
        cell_id="sq_test_cell",
        lat=10.0,
        lng=20.0,
        severity="high",
        change_score=0.7,
        fetch_thumb=False,
        context_thumb="data:image/png;base64,provided",
        context_thumb_source="seeded_cache",
        timelapse_b64="data:video/webm;base64,video",
        timelapse_source="replay",
    )

    item = gallery.get_gallery_item("sq_test_cell")

    assert item is not None
    assert item["context_thumb_source"] == "seeded_cache"
    assert item["timelapse_source"] == "replay"
