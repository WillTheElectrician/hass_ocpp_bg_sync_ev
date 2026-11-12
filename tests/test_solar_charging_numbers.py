"""Solar charging OCPP configuration number entities."""

from types import SimpleNamespace

import pytest

from custom_components.ocpp.enums import HAChargerDetails
from custom_components.ocpp.number import NUMBERS, ChargePointNumber


SOLAR_NUMBERS = {
    description.ocpp_key: description
    for description in NUMBERS
    if description.ocpp_key
    and description.ocpp_key
    in {"SolarMode", "SolarCurrentFromGrid", "SolarStableTime"}
}


def test_solar_number_descriptions():
    """Expose the spreadsheet's three solar keys with their default values."""
    assert {
        key: description.initial_value
        for key, description in SOLAR_NUMBERS.items()
    } == {
        "SolarMode": 0,
        "SolarCurrentFromGrid": 0,
        "SolarStableTime": 10,
    }
    assert len(SOLAR_NUMBERS) == 3
    assert all(description.model_gated for description in SOLAR_NUMBERS.values())


@pytest.mark.parametrize(
    ("ocpp_key", "value"),
    [
        ("SolarMode", 1),
        ("SolarCurrentFromGrid", 8),
        ("SolarStableTime", 30),
    ],
)
@pytest.mark.asyncio
async def test_solar_number_writes_ocpp_configuration(hass, ocpp_key, value):
    """Write integer inputs to the matching OCPP configuration key."""
    writes = []

    async def configure(key, config_value):
        writes.append((key, config_value))

    central_system = SimpleNamespace(
        cpids={"test_cpid": "test_cp"},
        charge_points={"test_cp": SimpleNamespace(configure=configure)},
    )
    entity = ChargePointNumber(
        hass,
        central_system,
        "test_cpid",
        SOLAR_NUMBERS[ocpp_key],
        connector_id=None,
        op_connector_id=0,
    )
    entity.async_write_ha_state = lambda: None

    await entity.async_set_native_value(value)

    assert writes == [(ocpp_key, str(value))]


def test_solar_numbers_only_available_on_supported_vendor_models(hass):
    """Do not surface vendor-specific controls for unrelated chargers."""
    model = None
    central_system = SimpleNamespace(
        get_metric=lambda cpid, metric: model
        if metric == HAChargerDetails.model.value
        else None,
        get_available=lambda *args: True,
    )
    entity = ChargePointNumber(
        hass,
        central_system,
        "test_cpid",
        SOLAR_NUMBERS["SolarMode"],
        connector_id=None,
        op_connector_id=0,
    )

    assert not entity.available
    model = "EVSC7S"
    assert entity.available
