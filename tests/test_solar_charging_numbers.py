"""Solar charging OCPP configuration number entities."""

from types import SimpleNamespace

import pytest

from custom_components.ocpp.number import (
    NUMBERS,
    REMOVED_NUMBER_KEYS,
    ChargePointNumber,
)
from custom_components.ocpp.switch import SWITCHES, ChargePointSwitch


SOLAR_NUMBERS = {
    description.ocpp_key: description
    for description in NUMBERS
    if description.ocpp_key
    and description.ocpp_key
    in {"SolarCurrentFromGrid", "SolarStableTime"}
}


def test_solar_number_descriptions():
    """Expose the two solar settings as writable number entities."""
    assert {
        key: description.initial_value
        for key, description in SOLAR_NUMBERS.items()
    } == {
        "SolarCurrentFromGrid": 0,
        "SolarStableTime": 10,
    }
    assert len(SOLAR_NUMBERS) == 2
    assert all(not description.model_gated for description in SOLAR_NUMBERS.values())


def test_solar_mode_is_an_on_off_switch():
    """Map the SolarMode OCPP integer values to switch states."""
    description = next(desc for desc in SWITCHES if desc.key == "solar_mode")

    assert description.ocpp_key == "SolarMode"
    assert description.default_state is False
    assert description.ocpp_on_value == "1"
    assert description.ocpp_off_value == "0"
    assert not description.model_gated
    assert "solar_mode" in REMOVED_NUMBER_KEYS


@pytest.mark.parametrize(
    ("ocpp_key", "value"), [("SolarCurrentFromGrid", 8), ("SolarStableTime", 30)]
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


@pytest.mark.asyncio
async def test_solar_mode_switch_sends_on_and_off_values(hass):
    """Turn SolarMode on with 1 and off with 0."""
    writes = []

    async def configure(key, value):
        writes.append((key, value))
        return "Accepted"

    async def get_configuration(key):
        return writes[-1][1]

    central_system = SimpleNamespace(
        cpids={"test_cpid": "test_cp"},
        charge_points={
            "test_cp": SimpleNamespace(
                configure=configure, get_configuration=get_configuration
            )
        },
        get_available=lambda *args: True,
    )
    description = next(desc for desc in SWITCHES if desc.key == "solar_mode")
    entity = ChargePointSwitch(central_system, "test_cpid", description)
    entity.async_write_ha_state = lambda: None

    await entity.async_turn_on()
    assert entity.is_on
    await entity.async_turn_off()
    assert not entity.is_on
    assert writes == [("SolarMode", "1"), ("SolarMode", "0")]


def test_solar_mode_switch_available_without_a_recognized_model():
    """Make SolarMode controllable when the charger is connected."""
    central_system = SimpleNamespace(get_available=lambda *args: True)
    description = next(desc for desc in SWITCHES if desc.key == "solar_mode")
    entity = ChargePointSwitch(central_system, "test_cpid", description)

    assert entity.available


@pytest.mark.parametrize("ocpp_key", ["SolarCurrentFromGrid", "SolarStableTime"])
def test_solar_numbers_available_without_a_recognized_model(hass, ocpp_key):
    """Use connection availability rather than a hard-coded model allowlist."""
    central_system = SimpleNamespace(
        get_available=lambda *args: True,
    )
    entity = ChargePointNumber(
        hass,
        central_system,
        "test_cpid",
        SOLAR_NUMBERS[ocpp_key],
        connector_id=None,
        op_connector_id=0,
    )

    assert entity.available
