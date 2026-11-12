"""Firmware update text and button entities."""

from types import SimpleNamespace

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.ocpp.button import BUTTONS, ChargePointButton
from custom_components.ocpp.enums import Profiles
from custom_components.ocpp.text import FirmwareURLText


def _firmware_button(hass, update_firmware, *, features=Profiles.FW):
    """Create a firmware button with a connected OCPP 1.6 charger."""
    cp = SimpleNamespace(
        _ocpp_version="1.6",
        update_firmware=update_firmware,
    )
    central = SimpleNamespace(
        hass=hass,
        cpids={"test_cpid": "test_cp"},
        charge_points={"test_cp": cp},
        get_available=lambda *args: True,
        get_supported_features=lambda cpid: features,
    )
    description = next(button for button in BUTTONS if button.key == "update_firmware")
    return ChargePointButton(central, "test_cpid", description)


def test_firmware_url_text_entity_is_on_charger_device():
    """Expose the input as a config entity for its charger."""
    entity = FirmwareURLText("test_cpid")

    assert entity.entity_id == "text.test_cpid_firmware_url"
    assert entity.device_info["identifiers"] == {("ocpp", "test_cpid")}
    assert entity.native_value == ""


@pytest.mark.asyncio
async def test_firmware_url_text_entity_saves_entered_value(hass):
    """Keep the URL entered on the charger device."""
    entity = FirmwareURLText("test_cpid")
    entity.hass = hass
    entity.async_write_ha_state = lambda: None

    await entity.async_set_value(" https://example.com/firmware.bin ")

    assert entity.native_value == "https://example.com/firmware.bin"


@pytest.mark.asyncio
async def test_firmware_button_sends_the_entered_url(hass):
    """Send the text entity value to the charger's firmware update method."""
    updates = []

    async def update_firmware(url):
        updates.append(url)
        return True

    button = _firmware_button(hass, update_firmware)
    hass.states.async_set(
        "text.test_cpid_firmware_url", "https://example.com/firmware.bin"
    )

    await button.async_press()

    assert updates == ["https://example.com/firmware.bin"]


@pytest.mark.asyncio
async def test_firmware_button_requires_a_url(hass):
    """Do not send an update request without a hosted firmware URL."""

    async def update_firmware(url):
        pytest.fail("Firmware update should not be sent")

    button = _firmware_button(hass, update_firmware)

    with pytest.raises(HomeAssistantError, match="Enter a firmware file URL"):
        await button.async_press()


def test_firmware_button_requires_firmware_management_support(hass):
    """Disable firmware updates when the charger lacks the OCPP profile."""

    async def update_firmware(url):
        pytest.fail("Firmware update should not be sent")

    button = _firmware_button(hass, update_firmware, features=Profiles.NONE)

    assert not button.available
