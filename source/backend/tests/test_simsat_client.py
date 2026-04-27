"""Tests for SimSat API client."""

import pytest

from core.simsat_client import (
    DataSource,
    EndpointType,
    ImageryRequest,
    SimSatClient,
    SimSatConfig,
    get_simsat_client,
    reset_simsat_client,
)


class TestSimSatConfig:
    """Tests for SimSatConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SimSatConfig()
        assert config.base_url == "http://localhost:8080"
        assert config.mapbox_token is None
        assert config.timeout_seconds == 30.0
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = SimSatConfig(
            base_url="http://custom:9000",
            mapbox_token="test_token",
            timeout_seconds=60.0,
        )
        assert config.base_url == "http://custom:9000"
        assert config.mapbox_token == "test_token"
        assert config.timeout_seconds == 60.0

    def test_from_env_accepts_mapbox_access_token(self, monkeypatch):
        """MAPBOX_ACCESS_TOKEN is the documented Mapbox variable."""
        monkeypatch.setenv("MAPBOX_ACCESS_TOKEN", "access_token")
        monkeypatch.delenv("MAPBOX_API_TOKEN", raising=False)

        config = SimSatConfig.from_env()

        assert config.mapbox_token == "access_token"

    def test_from_env_ignores_invalid_timeout(self, monkeypatch):
        """Bad timeout values should not break settings/status endpoints."""
        monkeypatch.setenv("SIMSAT_TIMEOUT", "not-a-number")

        config = SimSatConfig.from_env()

        assert config.timeout_seconds == 30.0

    def test_from_env_ignores_non_positive_timeout(self, monkeypatch):
        """Zero or negative timeout values fall back to the default."""
        monkeypatch.setenv("SIMSAT_TIMEOUT", "0")

        config = SimSatConfig.from_env()

        assert config.timeout_seconds == 30.0


class TestImageryRequest:
    """Tests for ImageryRequest."""
    
    def test_minimal_request(self):
        """Test minimal imagery request."""
        request = ImageryRequest(
            lat=-3.119,
            lng=-60.025,
            source=DataSource.SENTINEL,
        )
        assert request.lat == -3.119
        assert request.lng == -60.025
        assert request.source == DataSource.SENTINEL
        assert request.endpoint_type == EndpointType.CURRENT
    
    def test_full_request(self):
        """Test full imagery request with all parameters."""
        request = ImageryRequest(
            lat=-3.119,
            lng=-60.025,
            source=DataSource.MAPBOX,
            endpoint_type=EndpointType.HISTORICAL,
            date="2024-06-01",
            resolution=10,
            width=512,
            height=512,
        )
        assert request.date == "2024-06-01"
        assert request.resolution == 10
        assert request.width == 512
        assert request.height == 512


class TestSimSatClient:
    """Tests for SimSatClient."""
    
    def test_endpoint_paths(self):
        """Test endpoint path mapping."""
        client = SimSatClient(SimSatConfig())
        
        assert client._get_endpoint(DataSource.SENTINEL, EndpointType.CURRENT) == "/data/current/image/sentinel"
        assert client._get_endpoint(DataSource.SENTINEL, EndpointType.HISTORICAL) == "/data/image/sentinel"
        assert client._get_endpoint(DataSource.MAPBOX, EndpointType.CURRENT) == "/data/current/image/mapbox"
        assert client._get_endpoint(DataSource.MAPBOX, EndpointType.HISTORICAL) == "/data/image/mapbox"
        
        client.close()
    
    def test_build_params_minimal(self):
        """Test parameter building with minimal request."""
        client = SimSatClient(SimSatConfig())
        request = ImageryRequest(
            lat=-3.119,
            lng=-60.025,
            source=DataSource.SENTINEL,
        )
        params = client._build_params(request)
        
        assert params["lat"] == -3.119
        assert params["lng"] == -60.025
        assert "date" not in params
        assert "resolution" not in params
        
        client.close()
    
    def test_build_params_full(self):
        """Test parameter building with full request."""
        config = SimSatConfig(mapbox_token="test_token")
        client = SimSatClient(config)
        
        request = ImageryRequest(
            lat=-3.119,
            lng=-60.025,
            source=DataSource.MAPBOX,
            endpoint_type=EndpointType.HISTORICAL,
            date="2024-06-01",
            resolution=10,
            width=512,
            height=512,
        )
        params = client._build_params(request)
        
        assert params["lat"] == -3.119
        assert params["lng"] == -60.025
        assert params["date"] == "2024-06-01"
        assert params["resolution"] == 10
        assert params["width"] == 512
        assert params["height"] == 512
        assert params["token"] == "test_token"
        
        client.close()
    
    def test_mapbox_requires_token(self):
        """Test that Mapbox requests without token return error."""
        config = SimSatConfig(mapbox_token=None)
        client = SimSatClient(config)
        
        response = client.fetch_mapbox_current(lat=-3.119, lng=-60.025)
        
        assert response.success is False
        assert "token not configured" in response.error.lower()
        
        client.close()
    
    def test_context_manager(self):
        """Test client works as context manager."""
        with SimSatClient(SimSatConfig()) as client:
            assert client._client is None  # Lazy initialization
    
    def test_singleton_functions(self):
        """Test singleton client functions."""
        reset_simsat_client()
        
        client1 = get_simsat_client()
        client2 = get_simsat_client()
        
        assert client1 is client2
        
        reset_simsat_client()


class TestDataSourceEnum:
    """Tests for DataSource enum."""
    
    def test_values(self):
        """Test enum values."""
        assert DataSource.SENTINEL.value == "sentinel"
        assert DataSource.MAPBOX.value == "mapbox"


class TestEndpointTypeEnum:
    """Tests for EndpointType enum."""
    
    def test_values(self):
        """Test enum values."""
        assert EndpointType.HISTORICAL.value == "historical"
        assert EndpointType.CURRENT.value == "current"
