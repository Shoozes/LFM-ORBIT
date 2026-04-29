import logging
import os
from collections.abc import Mapping
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
"""Primary provider that routes through the official SimSat API."""

PROVIDER_SIMSAT_MAPBOX = "simsat_mapbox"
"""Optional provider - routes through SimSat's Mapbox imagery endpoint."""

PROVIDER_SENTINELHUB_DIRECT = "sentinelhub_direct"
"""Secondary provider – direct Sentinel Hub access for local dev/testing."""

PROVIDER_NASA_DIRECT = "nasa_api_direct"
"""Fallback provider – direct NASA API access when Sentinel Hub hits quota."""

PROVIDER_GEE = "gee"
"""Timelapse provider – Google Earth Engine Sentinel-2 SR 10m cloud-masked composites."""


VALID_PROVIDERS = (
    PROVIDER_SIMSAT_SENTINEL,
    PROVIDER_SIMSAT_MAPBOX,
    PROVIDER_SENTINELHUB_DIRECT,
    PROVIDER_NASA_DIRECT,
    PROVIDER_GEE,
)

# Scoring provider fallback order
PROVIDER_FALLBACK_ORDER = (
    PROVIDER_SIMSAT_SENTINEL,
    PROVIDER_SIMSAT_MAPBOX,
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

_SECRETS_DIR_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets"
_SECRETS_FILE_PATH = _SECRETS_DIR_PATH / "sentinel.txt"
_SH_SECRETS_FILE_PATH = _SECRETS_DIR_PATH / "sh.txt"
_SENTINEL_SECRETS_FILE_PATHS = (_SECRETS_FILE_PATH, _SH_SECRETS_FILE_PATH)
_NASA_SECRETS_FILE_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "nasa.txt"
_GEE_SECRETS_FILE_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "gee.txt"

_SENTINEL_CLIENT_ID_KEYS = (
    "SENTINEL_CLIENT_ID",
    "SENTINEL_HUB_CLIENT_ID",
    "SH_CLIENT_ID",
    "CLIENTID",
)
_SENTINEL_CLIENT_SECRET_KEYS = (
    "SENTINEL_CLIENT_SECRET",
    "SENTINEL_HUB_CLIENT_SECRET",
    "SH_CLIENT_SECRET",
    "CLIENT",
)
_SENTINEL_INSTANCE_ID_KEYS = (
    "SENTINEL_INSTANCE_ID",
    "SENTINEL_HUB_INSTANCE_ID",
    "SH_INSTANCE_ID",
    "SH_API_KEY",
    "API",
)

_SENTINEL_LABEL_ALIASES = {
    "API": "instance_id",
    "APIKEY": "instance_id",
    "API_KEY": "instance_id",
    "INSTANCE": "instance_id",
    "INSTANCEID": "instance_id",
    "INSTANCE_ID": "instance_id",
    "OGC": "instance_id",
    "WMS": "instance_id",
    "CLIENTID": "client_id",
    "CLIENT_ID": "client_id",
    "USER": "client_id",
    "USERID": "client_id",
    "USER_ID": "client_id",
    "OAUTH_CLIENT": "client_id",
    "OAUTH_CLIENT_ID": "client_id",
    "CLIENT": "client_secret",
    "CLIENTSECRET": "client_secret",
    "CLIENT_SECRET": "client_secret",
    "SECRET": "client_secret",
    "OAUTH": "client_secret",
    "OAUTHKEY": "client_secret",
    "OAUTH_KEY": "client_secret",
    "OAUTH_SECRET": "client_secret",
}


@dataclass(frozen=True)
class SentinelCredentials:
    """Resolved Sentinel Hub credentials (may be empty if unavailable)."""
    client_id: str
    client_secret: str
    source: str  # "env", "file", or "unavailable"
    instance_id: str = ""

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
        logger.debug("Unable to read secrets file %s", path, exc_info=True)
    return result


def _read_plain_secret_lines(path: Path) -> list[str]:
    """Read non-empty non-comment lines that are not KEY=VALUE pairs."""
    result: list[str] = []
    if not path.is_file():
        return result
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" in stripped:
                continue
            result.append(stripped.strip("\"'"))
    except OSError:
        logger.debug("Unable to read secrets file %s", path, exc_info=True)
    return result


def _parse_labeled_secret_lines(path: Path) -> dict[str, str]:
    """Parse local label/value secrets such as ``API <id>`` without logging values."""
    result = {"client_id": "", "client_secret": "", "instance_id": ""}
    if not path.is_file():
        return result
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" in stripped:
                continue
            normalized = stripped.replace(":", " ", 1)
            parts = normalized.split(maxsplit=1)
            if len(parts) != 2:
                continue
            label = parts[0].strip().upper().replace("-", "_")
            value = parts[1].strip().strip("\"'")
            target = _SENTINEL_LABEL_ALIASES.get(label)
            if target and value and not result[target]:
                result[target] = value
    except OSError:
        logger.debug("Unable to read secrets file %s", path, exc_info=True)
    return result


def _first_secret_value(values: Mapping[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = values.get(key, "").strip()
        if value:
            return value
    return ""


def _parse_sentinel_credentials_file(path: Path) -> tuple[str, str, str]:
    values = _parse_secrets_file(path)
    client_id = _first_secret_value(values, _SENTINEL_CLIENT_ID_KEYS)
    client_secret = _first_secret_value(values, _SENTINEL_CLIENT_SECRET_KEYS)
    instance_id = _first_secret_value(values, _SENTINEL_INSTANCE_ID_KEYS)
    if client_id and client_secret:
        return client_id, client_secret, instance_id

    labeled_values = _parse_labeled_secret_lines(path)
    client_id = client_id or labeled_values["client_id"]
    client_secret = client_secret or labeled_values["client_secret"]
    instance_id = instance_id or labeled_values["instance_id"]
    if client_id and client_secret:
        return client_id, client_secret, instance_id

    plain_lines = _read_plain_secret_lines(path)
    if len(plain_lines) >= 3:
        # Trial bundle format:
        #   line 1: API/OGC instance key
        #   line 2: OAuth secret
        #   line 3: OAuth client/user id
        return plain_lines[2].strip(), plain_lines[1].strip(), plain_lines[0].strip()
    if len(plain_lines) >= 2:
        # Legacy seed_sentinel_cache.py format was secret on line 1, id on line 2.
        return plain_lines[1].strip(), plain_lines[0].strip(), instance_id

    return "", "", instance_id


def resolve_sentinel_credentials(secrets_path: Path | None = None) -> SentinelCredentials:
    """Resolve Sentinel credentials using the defined priority order.

    Args:
        secrets_path: Override path for the secrets file (used in tests).
    """
    # 1. Environment variables first
    env_values = os.environ
    env_id = _first_secret_value(env_values, _SENTINEL_CLIENT_ID_KEYS)
    env_secret = _first_secret_value(env_values, _SENTINEL_CLIENT_SECRET_KEYS)
    env_instance_id = _first_secret_value(env_values, _SENTINEL_INSTANCE_ID_KEYS)
    if env_id and env_secret:
        logger.debug("Sentinel credentials resolved from environment variables")
        return SentinelCredentials(
            client_id=env_id,
            client_secret=env_secret,
            source="env",
            instance_id=env_instance_id,
        )

    # 2. File fallback (local/dev only)
    file_paths = (secrets_path,) if secrets_path is not None else _SENTINEL_SECRETS_FILE_PATHS
    checked_paths = []
    for file_path in file_paths:
        checked_paths.append(file_path)
        file_id, file_secret, file_instance_id = _parse_sentinel_credentials_file(file_path)
        if file_id and file_secret:
            logger.debug("Sentinel credentials resolved from %s", file_path)
            return SentinelCredentials(
                client_id=file_id,
                client_secret=file_secret,
                source="file",
                instance_id=file_instance_id,
            )

    # 3. Unavailable
    logger.debug("Sentinel credentials not available (checked env and %s)", checked_paths)
    return SentinelCredentials(client_id="", client_secret="", source="unavailable", instance_id="")


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
            logger.debug("Unable to read NASA secrets file %s", file_path, exc_info=True)

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
            logger.debug("Unable to read GEE secrets file %s", file_path, exc_info=True)

    return GeeCredentials(api_key="", client_id="", source="unavailable")


def resolve_active_provider() -> str:
    """Determine the active observation provider based on config and available credentials.

    Resolution rules:
      - If OBSERVATION_PROVIDER env var is set to a valid provider, use it directly.
      - If SimSat is enabled (SIMSAT_ENABLED=true), use the requested SimSat data source.
      - If Sentinel credentials are available, use sentinelhub_direct.
      - If NASA credentials are available, use nasa_api_direct.
      - Otherwise, stay on the safe SimSat/local fallback path.
    """
    explicit = os.environ.get("OBSERVATION_PROVIDER", "").strip()
    if explicit in VALID_PROVIDERS:
        return explicit

    if os.environ.get("SIMSAT_ENABLED", "").lower() in ("1", "true", "yes"):
        source = os.environ.get("SIMSAT_DATA_SOURCE", "").strip().lower()
        if source in ("mapbox", "simsat_mapbox"):
            return PROVIDER_SIMSAT_MAPBOX
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


@dataclass(frozen=True)
class DetectionConfig:
    min_quality_threshold: float
    ndvi_drop_threshold: float
    evi2_drop_threshold: float
    nir_drop_ratio_threshold: float
    nbr_drop_threshold: float
    ndmi_drop_threshold: float
    soil_ratio_spike_threshold: float
    high_confidence_target: float
    moderate_confidence_target: float
    critical_severity_threshold: float
    high_severity_threshold: float
    low_change_threshold: float
    confidence_base: float
    confidence_quality_multiplier: float
    confidence_penalty_low_change: float
    confidence_penalty_low_quality: float
    confidence_penalty_single_index: float
    confidence_bonus_pattern_match: float

DETECTION = DetectionConfig(
    min_quality_threshold=0.65,
    ndvi_drop_threshold=0.18,
    evi2_drop_threshold=0.15,
    nir_drop_ratio_threshold=0.25,
    nbr_drop_threshold=0.20,
    ndmi_drop_threshold=0.18,
    soil_ratio_spike_threshold=0.30,
    high_confidence_target=0.80,
    moderate_confidence_target=0.65,
    critical_severity_threshold=0.60,
    high_severity_threshold=0.45,
    low_change_threshold=0.12,
    confidence_base=0.58,
    confidence_quality_multiplier=0.32,
    confidence_penalty_low_change=0.08,
    confidence_penalty_low_quality=0.12,
    confidence_penalty_single_index=0.20,
    confidence_bonus_pattern_match=0.06,
)

# ---------------------------------------------------------------------------
# Runtime mode summary helpers (for startup logging and UI truth)
# ---------------------------------------------------------------------------

def get_runtime_mode_summary() -> dict:
    """Return a human-readable summary of the current runtime mode.

    Intended for startup logging and the provider-status API endpoint.
    """
    provider = REGION.observation_mode
    truth_mode = runtime_truth_mode_for_source(provider)
    return {
        "active_provider": provider,
        "runtime_truth_mode": truth_mode,
        "imagery_origin": imagery_origin_for_source(provider),
        "scoring_basis": scoring_basis_for_source(provider),
        "demo_mode_enabled": False,
        "imagery_backed_scoring_enabled": is_imagery_backed_scoring_enabled(),
    }


def normalize_runtime_truth_mode(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in {"live_imagery", "live"}:
        return "realtime"
    if text in {"seeded_replay", "demo_synthetic"}:
        return "replay" if text == "seeded_replay" else "fallback"
    if text in {"realtime", "replay", "fallback", "unknown"}:
        return text
    return "unknown"


def runtime_truth_mode_for_source(
    observation_source: str | None = None,
    *,
    demo_forced_anomaly: bool = False,
    mission_mode: str | None = None,
) -> str:
    """Classify whether an emitted signal is live, replayed from cache, or fallback."""
    if mission_mode == "replay":
        return "replay"

    source = str(observation_source or REGION.observation_mode or "").lower()
    if "seeded" in source or "replay" in source or "cache" in source:
        return "replay"
    if "fallback" in source or "mock" in source or "quality_gate" in source or "error" in source:
        return "fallback"
    if source == PROVIDER_SENTINELHUB_DIRECT or "sentinelhub_direct" in source:
        return "realtime"
    if "simsat" in source or "nasa" in source or "gibs" in source:
        return "realtime"
    if "gee" in source:
        return "realtime"
    if "semi_real" in source:
        return "fallback"
    if demo_forced_anomaly:
        return "fallback"
    return "unknown"


def imagery_origin_for_source(observation_source: str | None = None) -> str:
    source = str(observation_source or REGION.observation_mode or "").lower()
    if "seeded" in source or "replay" in source or "cache" in source:
        return "cached_api"
    if "sentinelhub" in source or source == PROVIDER_SENTINELHUB_DIRECT:
        return "sentinelhub"
    if "simsat" in source:
        return "simsat"
    if "nasa_gibs" in source or "gibs" in source:
        return "nasa_gibs"
    if "nasa_api" in source or source == PROVIDER_NASA_DIRECT:
        return "nasa_api"
    if "gee" in source:
        return "gee"
    if "esri" in source:
        return "esri_arcgis"
    if "fallback" in source or "quality_gate" in source or "error" in source or "semi_real" in source:
        return "fallback_none"
    return "unknown"


def scoring_basis_for_source(observation_source: str | None = None) -> str:
    source = str(observation_source or REGION.observation_mode or "").lower()
    truth_mode = runtime_truth_mode_for_source(source)
    if truth_mode == "fallback":
        return "fallback_none"
    if "sentinelhub_direct" in source or source == PROVIDER_SENTINELHUB_DIRECT or "gee" in source:
        return "multispectral_bands"
    if "simsat" in source or "nasa_api" in source or source == PROVIDER_NASA_DIRECT or "semi_real" in source:
        return "proxy_bands"
    if "seeded" in source or "replay" in source or "cache" in source or "gibs" in source or "esri" in source:
        return "visual_only"
    return "unknown"


def is_imagery_backed_scoring_enabled() -> bool:
    """Return True only when the active provider can supply real band values.

    Currently only ``sentinelhub_direct`` delivers true multispectral
    imagery-derived bands. SimSat and NASA paths can still use live imagery,
    but their scoring values are proxy bands rather than Sentinel-2 L2A bands.
    """
    return REGION.observation_mode == PROVIDER_SENTINELHUB_DIRECT
