"""Platform for Pixie Plus switch integration."""
from __future__ import annotations

from datetime import timedelta

import logging

import time

import async_timeout

from . import pixiepluslogin

import asyncio

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant import config_entries
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from typing import Any

from .const import DOMAIN, hardware_list, is_switch, has_two_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    # config: ConfigType,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:

    """Set up the Pixie Plus switch platform."""
    # Assigning configuration variables from HA config
    # The configuration check takes care they are present.

    # passing the Pixie Plus devices list with data about all the lights - list of dictionaries, eacy dictionary is a light

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # adding entities

    async_add_entities(
        PixiePlusSwitch(coordinator, idx)
        for idx, ent in enumerate(coordinator.data)
        if (str(ent["type"]).zfill(2) + str(ent["stype"]).zfill(2)) in is_switch
    )


class PixiePlusSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Representation of a Pixie Plus Light."""

    def __init__(self, coordinator, idx):

        """Initialize a Pixie Plus Light."""

        super().__init__(coordinator)
        self.idx = idx
        self._mac = self.coordinator.data[self.idx]["mac"]
        self._type = self.coordinator.data[self.idx]["type"]
        self._stype = self.coordinator.data[self.idx]["stype"]
        self._applicationid = self.coordinator.data[self.idx]["applicationid"]
        self._installationid = self.coordinator.data[self.idx]["installationid"]
        self._javascriptkey = self.coordinator.data[self.idx]["javascriptkey"]
        self._userid = self.coordinator.data[self.idx]["userid"]
        self._homeid = self.coordinator.data[self.idx]["homeid"]
        self._livegroup_objectid = self.coordinator.data[self.idx]["livegroup_objectid"]
        self._sessiontoken = self.coordinator.data[self.idx]["sessiontoken"]
        self._has_usb = self.coordinator.data[self.idx]["has_usb"]
        self._attr_has_entity_name = True
        self._state = self.coordinator.data[self.idx]["state"]
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self._has_usb_update = self.coordinator.data[self.idx]["has_usb_update"]
        self._model_no = str(self._type).zfill(2) + str(self._stype).zfill(2)
        self._side = self.coordinator.data[self.idx]["side"]
        if self._has_usb:
            self._attr_unique_id = self._mac + "_USB"
            self._attr_name = "USB"
        elif self._model_no in has_two_entities:
            self._master_device_name = self.coordinator.data[self.idx][
                "master_device_name"
            ]
            self._attr_unique_id = self._mac + self._side
            self._attr_name = self.coordinator.data[self.idx]["name"]
        else:
            self._attr_unique_id = self._mac
            self._attr_name = None

    async def async_added_to_hass(self):
        # Call when entity about to be added to hass

        await super().async_added_to_hass()
        state = await self.async_get_last_state()

        if self._has_usb:
            if state.state == "on":
                new_state = True
                self.coordinator.data[self.idx]["state"] = new_state
                self.coordinator.async_set_updated_data(self.coordinator.data)
            elif state.state == "off":
                new_state = ""
                self.coordinator.data[self.idx]["state"] = new_state
                self.coordinator.async_set_updated_data(self.coordinator.data)
            else:
                _LOGGER.info(f"Unknown last state")

    @property
    def device_info(self):

        if self._model_no in has_two_entities:
            name = self._master_device_name
        else:
            name = self.coordinator.data[self.idx]["name"]

        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._mac)
            },
            "name": name,
            "manufacturer": "SAL - Pixie Plus",
            "model": hardware_list[self._model_no],
            "via_device": (DOMAIN, "Pixie Plus Hub"),
        }

    @property
    def device_class(self):
        return "outlet"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        # name = self.coordinator.data[self.idx]["name"]
        # new_state = self.coordinator.data[self.idx]["state"]
        # _LOGGER.info(
        #    f"device {name} with has_usb of: {self._has_usb}, new state is {new_state}"
        # )

        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self._state = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

    '''
    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name
    '''

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Instructs the switch to turn on.

        other = ()

        await pixiepluslogin.change_light(self, "on", other)

        # assumes success - will get a push update after few second and will adjust according to the real state

        # _LOGGER.info(f"first updat, assuming success")
        self.coordinator.data[self.idx]["state"] = True
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""

        other = ()

        await pixiepluslogin.change_light(self, "00", other)

        self.coordinator.data[self.idx]["state"] = ""
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # await self.coordinator.async_request_refresh()
