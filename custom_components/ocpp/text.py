"""Text platform for OCPP charger settings."""

from __future__ import annotations

from typing import Final

from homeassistant.components.text import (
    DOMAIN as TEXT_DOMAIN,
    RestoreText,
    TextEntityDescription,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.util import slugify

from .const import CONF_CPID, CONF_CPIDS, DOMAIN

FIRMWARE_URL_DESCRIPTION: Final = TextEntityDescription(
    key="firmware_url",
    name="Firmware File URL",
    icon="mdi:link-variant",
    entity_category=EntityCategory.CONFIG,
    native_max=255,
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the firmware URL text input for each charger."""
    entities = []
    for charger in entry.data[CONF_CPIDS]:
        for cp_settings in charger.values():
            entities.append(FirmwareURLText(cp_settings[CONF_CPID]))
    async_add_devices(entities, False)


class FirmwareURLText(RestoreText):
    """Restorable firmware download URL for a charger."""

    entity_description = FIRMWARE_URL_DESCRIPTION
    _attr_has_entity_name = False

    def __init__(self, cpid: str) -> None:
        """Initialize the firmware URL input."""
        self.cpid = cpid
        self._attr_unique_id = ".".join(
            [TEXT_DOMAIN, DOMAIN, cpid, FIRMWARE_URL_DESCRIPTION.key]
        )
        self._attr_name = FIRMWARE_URL_DESCRIPTION.name
        self._attr_native_value = ""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cpid)},
            name=cpid,
        )
        self.entity_id = (
            f"{TEXT_DOMAIN}.{slugify(f'{cpid}_{FIRMWARE_URL_DESCRIPTION.key}')}"
        )

    async def async_added_to_hass(self) -> None:
        """Restore the previously entered firmware URL."""
        await super().async_added_to_hass()
        if restored := await self.async_get_last_text_data():
            self._attr_native_value = restored.native_value or ""

    async def async_set_value(self, value: str) -> None:
        """Save the firmware URL locally for the update button."""
        self._attr_native_value = value.strip()
        self.async_write_ha_state()
