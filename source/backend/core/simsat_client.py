"""
SimSat API Client

Provides integration with the official SimSat API (https://github.com/DPhi-Space/SimSat)
for fetching satellite imagery data from Sentinel-2 and Mapbox sources.

This module abstracts the SimSat API endpoints and provides a clean interface
for the observation loader to fetch real imagery data.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx


DEFAULT_SIMSAT_TIMEOUT_SECONDS = 30.0


def _parse_timeout(value: str | None) -> float:
    """Parse a positive timeout value while keeping bad env overrides non-fatal."""
    try:
        timeout = float(value or DEFAULT_SIMSAT_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        return DEFAULT_SIMSAT_TIMEOUT_SECONDS
    if timeout <= 0:
        return DEFAULT_SIMSAT_TIMEOUT_SECONDS
    return timeout


class DataSource(Enum):
    """Available data sources through SimSat API."""
    SENTINEL = "sentinel"
    MAPBOX = "mapbox"


class EndpointType(Enum):
    """Types of SimSat API endpoints."""
    HISTORICAL = "historical"
    CURRENT = "current"


@dataclass
class SimSatConfig:
    """Configuration for SimSat API client."""
    base_url: str = "http://localhost:8080"
    mapbox_token: Optional[str] = None
    timeout_seconds: float = 30.0
    
    @classmethod
    def from_env(cls) -> "SimSatConfig":
        """Create configuration from environment variables."""
        return cls(
            base_url=os.environ.get("SIMSAT_BASE_URL", "http://localhost:8080"),
            mapbox_token=os.environ.get("MAPBOX_ACCESS_TOKEN") or os.environ.get("MAPBOX_API_TOKEN"),
            timeout_seconds=_parse_timeout(os.environ.get("SIMSAT_TIMEOUT")),
        )


@dataclass
class ImageryRequest:
    """Request parameters for fetching imagery."""
    lat: float
    lng: float
    source: DataSource
    endpoint_type: EndpointType = EndpointType.CURRENT
    date: Optional[str] = None  # ISO format for historical queries
    resolution: Optional[int] = None  # Meters per pixel
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class ImageryResponse:
    """Response from SimSat API containing imagery data."""
    success: bool
    source: str
    endpoint_type: str
    lat: float
    lng: float
    image_data: Optional[bytes] = None
    metadata: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class SimSatClientError(Exception):
    """Exception raised for SimSat client errors."""


class SimSatClient:
    """
    Client for interacting with the SimSat API.
    
    The SimSat API provides access to:
    - Sentinel-2 multispectral imagery (10m resolution, 3-5 day revisit)
    - Mapbox high-resolution imagery (10-30cm resolution, static)
    
    Endpoints:
    - /data/image/sentinel - Historical Sentinel-2 imagery
    - /data/image/mapbox - Historical Mapbox imagery
    - /data/current/image/sentinel - Live Sentinel-2 imagery
    - /data/current/image/mapbox - Live Mapbox imagery
    """
    
    ENDPOINT_PATHS = {
        (DataSource.SENTINEL, EndpointType.HISTORICAL): "/data/image/sentinel",
        (DataSource.SENTINEL, EndpointType.CURRENT): "/data/current/image/sentinel",
        (DataSource.MAPBOX, EndpointType.HISTORICAL): "/data/image/mapbox",
        (DataSource.MAPBOX, EndpointType.CURRENT): "/data/current/image/mapbox",
    }
    
    def __init__(self, config: Optional[SimSatConfig] = None):
        """
        Initialize the SimSat client.
        
        Args:
            config: Optional configuration. If not provided, loads from environment.
        """
        self.config = config or SimSatConfig.from_env()
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
        return self._client
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
    
    def __enter__(self) -> "SimSatClient":
        return self
    
    def __exit__(self, *args: Any) -> None:
        self.close()
    
    def _get_endpoint(self, source: DataSource, endpoint_type: EndpointType) -> str:
        """Get the API endpoint path for the given source and type."""
        key = (source, endpoint_type)
        if key not in self.ENDPOINT_PATHS:
            raise SimSatClientError(f"Unknown endpoint: {source.value}/{endpoint_type.value}")
        return self.ENDPOINT_PATHS[key]
    
    def _build_params(self, request: ImageryRequest) -> dict[str, Any]:
        """Build query parameters for the API request."""
        params: dict[str, Any] = {
            "lat": request.lat,
            "lng": request.lng,
        }
        
        if request.date is not None:
            params["date"] = request.date
        
        if request.resolution is not None:
            params["resolution"] = request.resolution
        
        if request.width is not None:
            params["width"] = request.width
        
        if request.height is not None:
            params["height"] = request.height
        
        # Add Mapbox token if required
        if request.source == DataSource.MAPBOX and self.config.mapbox_token:
            params["token"] = self.config.mapbox_token
        
        return params
    
    def fetch_imagery(self, request: ImageryRequest) -> ImageryResponse:
        """
        Fetch imagery from SimSat API.
        
        Args:
            request: The imagery request parameters.
            
        Returns:
            ImageryResponse with image data or error information.
        """
        endpoint = self._get_endpoint(request.source, request.endpoint_type)
        params = self._build_params(request)
        
        try:
            response = self.client.get(endpoint, params=params)
            
            if response.status_code == 200:
                return ImageryResponse(
                    success=True,
                    source=request.source.value,
                    endpoint_type=request.endpoint_type.value,
                    lat=request.lat,
                    lng=request.lng,
                    image_data=response.content,
                    metadata={
                        "content_type": response.headers.get("content-type"),
                        "content_length": len(response.content),
                    },
                )
            else:
                return ImageryResponse(
                    success=False,
                    source=request.source.value,
                    endpoint_type=request.endpoint_type.value,
                    lat=request.lat,
                    lng=request.lng,
                    error=f"HTTP {response.status_code}: {response.text}",
                )
                
        except httpx.TimeoutException as e:
            return ImageryResponse(
                success=False,
                source=request.source.value,
                endpoint_type=request.endpoint_type.value,
                lat=request.lat,
                lng=request.lng,
                error=f"Request timeout: {e}",
            )
        except httpx.RequestError as e:
            return ImageryResponse(
                success=False,
                source=request.source.value,
                endpoint_type=request.endpoint_type.value,
                lat=request.lat,
                lng=request.lng,
                error=f"Request error: {e}",
            )
    
    def fetch_sentinel_current(
        self, lat: float, lng: float, resolution: Optional[int] = None
    ) -> ImageryResponse:
        """
        Fetch current Sentinel-2 imagery.
        
        Args:
            lat: Latitude of the center point.
            lng: Longitude of the center point.
            resolution: Optional resolution in meters per pixel.
            
        Returns:
            ImageryResponse with image data or error.
        """
        return self.fetch_imagery(ImageryRequest(
            lat=lat,
            lng=lng,
            source=DataSource.SENTINEL,
            endpoint_type=EndpointType.CURRENT,
            resolution=resolution,
        ))
    
    def fetch_sentinel_historical(
        self, lat: float, lng: float, date: str, resolution: Optional[int] = None
    ) -> ImageryResponse:
        """
        Fetch historical Sentinel-2 imagery.
        
        Args:
            lat: Latitude of the center point.
            lng: Longitude of the center point.
            date: ISO format date for the historical query.
            resolution: Optional resolution in meters per pixel.
            
        Returns:
            ImageryResponse with image data or error.
        """
        return self.fetch_imagery(ImageryRequest(
            lat=lat,
            lng=lng,
            source=DataSource.SENTINEL,
            endpoint_type=EndpointType.HISTORICAL,
            date=date,
            resolution=resolution,
        ))
    
    def fetch_mapbox_current(
        self, lat: float, lng: float, width: Optional[int] = None, height: Optional[int] = None
    ) -> ImageryResponse:
        """
        Fetch current Mapbox imagery.
        
        Args:
            lat: Latitude of the center point.
            lng: Longitude of the center point.
            width: Optional image width in pixels.
            height: Optional image height in pixels.
            
        Returns:
            ImageryResponse with image data or error.
        """
        if not self.config.mapbox_token:
            return ImageryResponse(
                success=False,
                source=DataSource.MAPBOX.value,
                endpoint_type=EndpointType.CURRENT.value,
                lat=lat,
                lng=lng,
                error="Mapbox API token not configured. Set MAPBOX_ACCESS_TOKEN or MAPBOX_API_TOKEN.",
            )
        
        return self.fetch_imagery(ImageryRequest(
            lat=lat,
            lng=lng,
            source=DataSource.MAPBOX,
            endpoint_type=EndpointType.CURRENT,
            width=width,
            height=height,
        ))
    
    def fetch_mapbox_historical(
        self, lat: float, lng: float, date: str, width: Optional[int] = None, height: Optional[int] = None
    ) -> ImageryResponse:
        """
        Fetch historical Mapbox imagery.
        
        Args:
            lat: Latitude of the center point.
            lng: Longitude of the center point.
            date: ISO format date for the historical query.
            width: Optional image width in pixels.
            height: Optional image height in pixels.
            
        Returns:
            ImageryResponse with image data or error.
        """
        if not self.config.mapbox_token:
            return ImageryResponse(
                success=False,
                source=DataSource.MAPBOX.value,
                endpoint_type=EndpointType.HISTORICAL.value,
                lat=lat,
                lng=lng,
                error="Mapbox API token not configured. Set MAPBOX_ACCESS_TOKEN or MAPBOX_API_TOKEN.",
            )
        
        return self.fetch_imagery(ImageryRequest(
            lat=lat,
            lng=lng,
            source=DataSource.MAPBOX,
            endpoint_type=EndpointType.HISTORICAL,
            date=date,
            width=width,
            height=height,
        ))
    
    def is_available(self) -> bool:
        """
        Check if the SimSat API is available.
        
        Returns:
            True if the API is reachable, False otherwise.
        """
        try:
            response = self.client.get("/health", timeout=5.0)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException, ValueError):
            return False


# Singleton instance for convenience
_default_client: Optional[SimSatClient] = None


def get_simsat_client() -> SimSatClient:
    """Get the default SimSat client instance."""
    global _default_client
    if _default_client is None:
        _default_client = SimSatClient()
    return _default_client


def reset_simsat_client() -> None:
    """Reset the default SimSat client instance."""
    global _default_client
    if _default_client is not None:
        _default_client.close()
        _default_client = None
