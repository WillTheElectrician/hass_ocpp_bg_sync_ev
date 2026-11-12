"""Button platform for ocpp."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.util import slugify

from .api import CentralSystem
from .const import (
    CONF_CPID,
    CONF_CPIDS,
    CONF_NUM_CONNECTORS,
    DATA_UPDATED,
    DEFAULT_NUM_CONNECTORS,
    DOMAIN,
)
from .enums import HAChargerServices, Profiles


@dataclass
class OcppButtonDescription(ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_action: str | None = None
    per_connector: bool = False


BUTTONS: Final = [
    OcppButtonDescription(
        key="reset",
        name="Restart Charger",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=HAChargerServices.service_reset.name,
        per_connector=False,
    ),
    OcppButtonDescription(
        key="unlock",
        name="Unlock Connector",
        device_class=None,
        entity_category=EntityCategory.CONFIG,
        press_action=HAChargerServices.service_unlock.name,
        per_connector=True,
    ),
    OcppButtonDescription(
        key="update_firmware",
        name="Update Firmware",
        icon="mdi:package-up",
        entity_category=EntityCategory.CONFIG,
        per_connector=False,
    ),
]


async def async_setup_entry(hass, entry, async_add_devices):
    """Configure the Button platform."""
    central_system: CentralSystem = hass.data[DOMAIN][entry.entry_id]
    entities: list[ChargePointButton] = []
    ent_reg = er.async_get(hass)

    for charger in entry.data[CONF_CPIDS]:
        cp_id_settings = list(charger.values())[0]
        cpid = cp_id_settings[CONF_CPID]

        num_connectors = 1
        for item in entry.data.get(CONF_CPIDS, []):
            for _, cfg in item.items():
                if cfg.get(CONF_CPID) == cpid:
                    num_connectors = int(
                        cfg.get(CONF_NUM_CONNECTORS, DEFAULT_NUM_CONNECTORS)
                    )
                    break
            else:
                continue
            break

        if num_connectors > 1:
            for desc in BUTTONS:
                if not desc.per_connector:
                    continue
                uid_flat = ".".join([BUTTON_DOMAIN, DOMAIN, cpid, desc.key])
                stale_eid = ent_reg.async_get_entity_id(BUTTON_DOMAIN, DOMAIN, uid_flat)
                if stale_eid:
                    ent_reg.async_remove(stale_eid)

        for desc in BUTTONS:
            if desc.per_connector:
                if num_connectors > 1:
                    for connector_id in range(1, num_connectors + 1):
                        entities.append(
                            ChargePointButton(
                                central_system=central_system,
                                cpid=cpid,
                                description=desc,
                                connector_id=connector_id,
                                op_connector_id=connector_id,
                            )
                        )
                else:
                    entities.append(
                        ChargePointButton(
                            central_system=central_system,
                            cpid=cpid,
                            description=desc,
                            connector_id=None,
                            op_connector_id=1,
                        )
                    )
            else:
                entities.append(
                    ChargePointButton(
                        central_system=central_system,
                        cpid=cpid,
                        description=desc,
                        connector_id=None,
                        op_connector_id=None,
                    )
                )

    async_add_devices(entities, False)


class ChargePointButton(ButtonEntity):
    """Individual button for charge point."""

    _attr_has_entity_name = False
    entity_description: OcppButtonDescription

    def __init__(
        self,
        central_system: CentralSystem,
        cpid: str,
        description: OcppButtonDescription,
        connector_id: int | None = None,
        op_connector_id: int | None = None,
    ):
        """Instantiate instance of a ChargePointButton."""
        self.cpid = cpid
        self.central_system = central_system
        self.entity_description = description
        self.connector_id = connector_id
        self._op_connector_id = op_connector_id
        parts = [BUTTON_DOMAIN, DOMAIN, cpid, description.key]
        if self.connector_id:
            parts.insert(3, f"conn{self.connector_id}")
        self._attr_unique_id = ".".join(parts)
        self._attr_name = self.entity_description.name
        if self.connector_id:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{cpid}-conn{self.connector_id}")},
                name=f"{cpid} Connector {self.connector_id}",
                via_device=(DOMAIN, cpid),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, cpid)},
                name=cpid,
            )
        if self.connector_id is not None:
            object_id = f"{self.cpid}_connector_{self.connector_id}_{self.entity_description.key}"
        else:
            object_id = f"{self.cpid}_{self.entity_description.key}"
        self.entity_id = f"{BUTTON_DOMAIN}.{slugify(object_id)}"

    @property
    def available(self) -> bool:
        """Return charger availability."""
        if self.entity_description.key == "update_firmware":
            cp_id = self.central_system.cpids.get(self.cpid, self.cpid)
            cp = self.central_system.charge_points.get(cp_id)
            return bool(
                self.central_system.get_available(self.cpid, None)
                and cp is not None
                and cp._ocpp_version == "1.6"
                and self.central_system.get_supported_features(self.cpid) & Profiles.FW
            )
        return self.central_system.get_available(self.cpid, self._op_connector_id)

    async def async_press(self) -> None:
        """Triggers the charger press action service."""
        if self.entity_description.key == "update_firmware":
            url_entity_id = f"text.{slugify(f'{self.cpid}_firmware_url')}"
            url_state = self.central_system.hass.states.get(url_entity_id)
            firmware_url = (
                url_state.state.strip()
                if url_state
                and url_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                else ""
            )
            if not firmware_url:
                raise HomeAssistantError(
                    "Enter a firmware file URL before starting the update."
                )

            cp_id = self.central_system.cpids.get(self.cpid, self.cpid)
            cp = self.central_system.charge_points.get(cp_id)
            if cp is None or cp._ocpp_version != "1.6":
                raise HomeAssistantError(
                    "Firmware updates are not available for this charger."
                )
            if not (
                self.central_system.get_supported_features(self.cpid) & Profiles.FW
            ):
                raise HomeAssistantError(
                    "This charger does not support OCPP firmware updates."
                )
            if not await cp.update_firmware(firmware_url):
                raise HomeAssistantError(
                    "The charger could not start the firmware update."
                )
            return

        await self.central_system.set_charger_state(
            self.cpid,
            self.entity_description.press_action,
            connector_id=self._op_connector_id,
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()

        @callback
        def _maybe_update(*args):
            """Handle dispatcher updates."""
            active_lookup = None
            if args:
                try:
                    active_lookup = set(args[0])
                except Exception:
                    active_lookup = None

            if active_lookup is None or self.entity_id in active_lookup:
                self.async_schedule_update_ha_state(True)

        # Register dispatcher listener
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DATA_UPDATED, _maybe_update)
        )

        # Ensure button is shown as available after reload
        self.async_schedule_update_ha_state(True)
