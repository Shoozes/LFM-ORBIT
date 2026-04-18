import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider name constants
# ---------------------------------------------------------------------------
# These are the only valid provider identifiers across the entire codebase.
# Every observation_source label, config value, and doc reference must use
# one of these exact strings.

PROVIDER_SIMSAT_SENTINEL = "simsat_sentinel"
"""Primary provider – routes through the official SimSat API (hackathon submission path)."""

PROVIDER_SENTINELHUB_DIRECT = "sentinelhub_direct"
"""Secondary provider – direct Sentinel Hub access for local dev/testing."""

PROVIDER_NASA_DIRECT = "nasa_api_direct"
"""Fallback provider – direct NASA API access when Sentinel Hub hits quota."""

PROVIDER_GEE = "gee"
"""Timelapse provider – Google Earth Engine Sentinel-2 SR 10m cloud-masked composites."""


VALID_PROVIDERS = (
    PROVIDER_SIMSAT_SENTINEL,
    PROVIDER_SENTINELHUB_DIRECT,
    PROVIDER_NASA_DIRECT,
    PROVIDER_GEE,
)

# Scoring provider fallback order
PROVIDER_FALLBACK_ORDER = (
    PROVIDER_SIMSAT_SENTINEL,
    PROVIDER_SENTINELHUB_DIRECT,
    PROVIDER_NASA_DIRECT,
)

# Timelapse provider fallback order (best quality first)
TIMELAPSE_PROVIDER_ORDER = (
    PROVIDER_GEE,       # Sentinel-2 SR 10m cloud-masked
    PROVIDER_NASA_DIRECT,  # HLS 30m / MODIS 250m via GIBS
)


# ---------------------------------------------------------------------------
# Sentinel & NASA secret/config resolution
# ---------------------------------------------------------------------------
# Resolution order:
#   1. Environment variable
#   2. File fallback         .tools/.secrets/*.txt  (local/dev only)
#   3. Unavailable
# ---------------------------------------------------------------------------

_SECRETS_FILE_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "sentinel.txt"
_NASA_SECRETS_FILE_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "nasa.txt"
_GEE_SECRETS_FILE_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "gee.txt"


@dataclass(frozen=True)
class SentinelCredentials:
    """Resolved Sentinel Hub credentials (may be empty if unavailable)."""
    client_id: str
    client_secret: str
    source: str  # "env", "file", or "unavailable"

    @property
    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)


def _parse_secrets_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE secrets file. Ignores blank lines and comments."""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            # Strip whitespace then remove surrounding quotes (single or double)
            result[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return result


def resolve_sentinel_credentials(secrets_path: Path | None = None) -> SentinelCredentials:
    """Resolve Sentinel credentials using the defined priority order.

    Args:
        secrets_path: Override path for the secrets file (used in tests).
    """
    # 1. Environment variables first
    env_id = os.environ.get("SENTINEL_CLIENT_ID", "").strip()
    env_secret = os.environ.get("SENTINEL_CLIENT_SECRET", "").strip()
    if env_id and env_secret:
        logger.debug("Sentinel credentials resolved from environment variables")
        return SentinelCredentials(client_id=env_id, client_secret=env_secret, source="env")

    # 2. File fallback (local/dev only)
    file_path = secrets_path if secrets_path is not None else _SECRETS_FILE_PATH
    file_values = _parse_secrets_file(file_path)
    file_id = file_values.get("SENTINEL_CLIENT_ID", "").strip()
    file_secret = file_values.get("SENTINEL_CLIENT_SECRET", "").strip()
    if file_id and file_secret:
        logger.debug("Sentinel credentials resolved from %s", file_path)
        return SentinelCredentials(client_id=file_id, client_secret=file_secret, source="file")

    # 3. Unavailable
    logger.debug("Sentinel credentials not available (checked env and %s)", file_path)
    return SentinelCredentials(client_id="", client_secret="", source="unavailable")


@dataclass(frozen=True)
class NasaCredentials:
    """Resolved NASA credentials (api_key)."""
    api_key: str
    source: str

    @property
    def available(self) -> bool:
        return bool(self.api_key)

def resolve_nasa_credentials(secrets_path: Path | None = None) -> NasaCredentials:
    """Resolve NASA API credentials using environment or file."""
    env_key = os.environ.get("NASA_API_KEY", "").strip()
    if env_key:
        return NasaCredentials(api_key=env_key, source="env")

    # The file contains only the key or KEY=value
    file_path = secrets_path if secrets_path is not None else _NASA_SECRETS_FILE_PATH
    if file_path.is_file():
        try:
            content = file_path.read_text(encoding="utf-8").strip()
            if "=" in content:
                key = _parse_secrets_file(file_path).get("NASA_API_KEY", "").strip()
            else:
                key = content.splitlines()[0].strip()
            if key:
                return NasaCredentials(api_key=key, source="file")
        except OSError:
            pass

    return NasaCredentials(api_key="", source="unavailable")


@dataclass(frozen=True)
class GeeCredentials:
    """Resolved Google Earth Engine credentials."""
    api_key: str
    client_id: str
    source: str

    @property
    def available(self) -> bool:
        return bool(self.api_key)


def resolve_gee_credentials(secrets_path: Path | None = None) -> GeeCredentials:
    """Resolve GEE credentials from env or .tools/.secrets/gee.txt."""
    env_key = os.environ.get("GEE_API_KEY", "").strip()
    env_cid = os.environ.get("GEE_CLIENT_ID", "").strip()
    if env_key:
        return GeeCredentials(api_key=env_key, client_id=env_cid, source="env")

    file_path = secrets_path if secrets_path is not None else _GEE_SECRETS_FILE_PATH
    if file_path.is_file():
        try:
            lines = [l.strip() for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                api_key = lines[0]
                client_id = lines[1] if len(lines) > 1 else ""
                return GeeCredentials(api_key=api_key, client_id=client_id, source="file")
        except OSError:
            pass

    return GeeCredentials(api_key="", client_id="", source="unavailable")


def resolve_active_provider() -> str:
    """Determine the active observation provider based on config and available credentials.

    Resolution rules:
      - If OBSERVATION_PROVIDER env var is set to a valid provider, use it directly.
      - If SimSat is enabled (SIMSAT_ENABLED=true), use simsat_sentinel.
      - If Sentinel credentials are available, use sentinelhub_direct.
      - Otherwise, fall back to semi_real_loader_v1.
    """
    explicit = os.environ.get("OBSERVATION_PROVIDER", "").strip()
    if explicit in VALID_PROVIDERS:
        return explicit

    if os.environ.get("SIMSAT_ENABLED", "").lower() in ("1", "true", "yes"):
        return PROVIDER_SIMSAT_SENTINEL

    # Check OAuth creds — no cross-module imports to keep config.py dependency-free
    creds = resolve_sentinel_credentials()
    if creds.available:
        return PROVIDER_SENTINELHUB_DIRECT
        
    nasa_creds = resolve_nasa_credentials()
    if nasa_creds.available:
        return PROVIDER_NASA_DIRECT

    return PROVIDER_SIMSAT_SENTINEL


# ---------------------------------------------------------------------------
# Region configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegionConfig:
    region_id: str
    display_name: str
    center_lat: float
    center_lng: float
    bbox: tuple[float, float, float, float]
    grid_resolution: int
    ring_size: int
    scan_delay_seconds: float
    anomaly_threshold: float
    estimated_frame_size_mb: float
    observation_mode: str
    before_label: str
    after_label: str
    disturbance_seed_threshold: float
    cloud_seed_threshold: float
    map_zoom: float



_ACTIVE_PROVIDER = resolve_active_provider()

REGION = RegionConfig(
    region_id="amazonas_region_alpha",
    display_name="Amazonas Focus Region",
    center_lat=-3.119,
    center_lng=-60.025,
    bbox=(-60.95, -3.95, -59.10, -2.15),
    grid_resolution=5,
    ring_size=6,
    scan_delay_seconds=1.5 if _ACTIVE_PROVIDER == PROVIDER_SENTINELHUB_DIRECT else 0.05,
    anomaly_threshold=0.32,
    estimated_frame_size_mb=5.0,
    observation_mode=_ACTIVE_PROVIDER,
    before_label="2024-06",
    after_label="2025-06",
    disturbance_seed_threshold=0.955,
    cloud_seed_threshold=0.975,
    map_zoom=6.0,
)


# ---------------------------------------------------------------------------
# Runtime mode summary helpers (for startup logging and UI truth)
# ---------------------------------------------------------------------------

def get_runtime_mode_summary() -> dict:
    """Return a human-readable summary of the current runtime mode.

    Intended for startup logging and the provider-status API endpoint.
    """
    provider = REGION.observation_mode
    return {
        "active_provider": provider,
        "imagery_backed_scoring_enabled": provider != PROVIDER_SIMSAT_SENTINEL,
    }


def is_imagery_backed_scoring_enabled() -> bool:
    """Return True only when the active provider can supply real band values.

    Currently only ``sentinelhub_direct`` delivers true imagery-derived bands.
    SimSat transport uses semi-real bands — the source label says *transport*,
    not *real_band_scoring*. NASA API uses simulated bands backed by RGB retrieval.
    """
    return REGION.observation_mode == PROVIDER_SENTINELHUB_DIRECT


def should_describe_demo_as_semi_real() -> bool:
    """Return True when the judge-facing demo should be described as semi-real.

    Stays True unless true imagery-derived scoring is explicitly active and validated.
    """
    return not is_imagery_backed_scoring_enabled()