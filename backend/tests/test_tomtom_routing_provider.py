from unittest.mock import MagicMock, patch

import pytest

from app.providers.base import RouteInput
from app.providers.routing.tomtom_provider import TomTomRoutingNotPossibleError, TomTomRoutingProvider


def _mock_response(json_payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_payload
    response.raise_for_status = MagicMock()
    return response


def test_calculate_route_parses_tomtom_response() -> None:
    provider = TomTomRoutingProvider(api_key="test-key")
    payload = {"routes": [{"summary": {"lengthInMeters": 105320, "travelTimeInSeconds": 5400}}]}

    with patch("app.providers.routing.tomtom_provider.httpx.get", return_value=_mock_response(payload)) as mock_get:
        result = provider.calculate_route(
            RouteInput(origin_lat=52.5, origin_lon=13.4, destination_lat=53.5, destination_lon=10.0, profile="truck")
        )

    assert result.distance_km == 105.32
    assert result.duration_minutes == 90
    assert result.provider == "tomtom"
    assert result.profile == "truck"

    called_url = mock_get.call_args.args[0]
    assert "52.5,13.4:53.5,10.0" in called_url
    assert mock_get.call_args.kwargs["params"]["travelMode"] == "truck"
    assert mock_get.call_args.kwargs["params"]["key"] == "test-key"


def test_calculate_route_uses_haversine_for_air_profile_without_calling_api() -> None:
    provider = TomTomRoutingProvider(api_key="test-key")

    with patch("app.providers.routing.tomtom_provider.httpx.get") as mock_get:
        result = provider.calculate_route(
            RouteInput(origin_lat=52.5, origin_lon=13.4, destination_lat=52.5, destination_lon=13.4, profile="air")
        )

    mock_get.assert_not_called()
    assert result.provider == "haversine"
    assert result.distance_km == 0.0


def test_calculate_route_raises_when_no_routes_returned() -> None:
    provider = TomTomRoutingProvider(api_key="test-key")

    with patch("app.providers.routing.tomtom_provider.httpx.get", return_value=_mock_response({"routes": []})):
        with pytest.raises(TomTomRoutingNotPossibleError):
            provider.calculate_route(
                RouteInput(origin_lat=52.5, origin_lon=13.4, destination_lat=53.5, destination_lon=10.0, profile="truck")
            )
