"""Platform for Pixie Plus light integration."""
from __future__ import annotations

from datetime import timedelta

import logging

import time

import async_timeout

from . import pixiepluslogin

import asyncio

from homeassistant.components.light import ATTR_BRIGHTNESS, PLATFORM_SCHEMA, LightEntity
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
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

from typing import Any

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    # config: ConfigType,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:

    """Set up the Pixie Plus Light platform."""
    # Assigning configuration variables from HA config
    # The configuration check takes care they are present.

    # passing the Pixie Plus devices list with data about all the lights - list of dictionaries, eacy dictionary is a light
    devices_list = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = MyCoordinator(hass, devices_list)

    await coordinator.async_config_entry_first_refresh()

    # adding entities
    async_add_entities(
        PixiePlusLight(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    )

    # calling websocket connection to get push updates
    asyncio.create_task(
        pixiepluslogin.pixie_websocket_connect(
            devices_list[0]["applicationid"],
            devices_list[0]["installationid"],
            devices_list[0]["javascriptkey"],
            devices_list[0]["sessiontoken"],
            devices_list[0]["userid"],
            devices_list[0]["homeid"],
            devices_list[0]["livegroup_objectid"],
            coordinator,
            hass,
        )
    )


class MyCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, my_api):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Pixie Plus",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=15),
        )
        self.my_api = my_api
        self._applicationid = self.my_api[0]["applicationid"]
        self._installationid = self.my_api[0]["installationid"]
        self._javascriptkey = self.my_api[0]["javascriptkey"]
        self._sessiontoken = self.my_api[0]["sessiontoken"]
        self._userid = self.my_api[0]["userid"]
        self._homeid = self.my_api[0]["homeid"]
        self.livegroup_objectid = self.my_api[0]["livegroup_objectid"]

    async def _async_update_data(self):

        ID_param = {
            "_ApplicationId": self._applicationid,
            "_ClientVersion": "js1.9.2",
            "_InstallationId": self._installationid,
            "_JavaScriptKey": self._javascriptkey,
            "_SessionToken": self._sessiontoken,
        }

        session_data = {
            "userid": self._userid,
            "homeid": self._homeid,
            "livegroup_objectid": self.livegroup_objectid,
            "applicationid": self._applicationid,
            "installationid": self._installationid,
            "javascriptkey": self._javascriptkey,
            "sessiontoken": self._sessiontoken,
        }

        try:
            devices_list = await pixiepluslogin.getdevices(session_data, ID_param)
        except:
            _LOGGER.warning("Could not process devices update")

        return devices_list


class PixiePlusLight(CoordinatorEntity, LightEntity):
    """Representation of a Pixie Plus Light."""

    def __init__(self, coordinator, idx):

        """Initialize a Pixie Plus Light."""

        # self._light = light
        super().__init__(coordinator)
        self.idx = idx
        self._name = self.coordinator.data[self.idx]["name"]
        self._mac = self.coordinator.data[self.idx]["mac"]
        self._state = self.coordinator.data[self.idx]["state"]
        self._applicationid = self.coordinator.data[self.idx]["applicationid"]
        self._installationid = self.coordinator.data[self.idx]["installationid"]
        self._javascriptkey = self.coordinator.data[self.idx]["javascriptkey"]
        self._userid = self.coordinator.data[self.idx]["userid"]
        self._homeid = self.coordinator.data[self.idx]["homeid"]
        self._livegroup_objectid = self.coordinator.data[self.idx]["livegroup_objectid"]
        self._sessiontoken = self.coordinator.data[self.idx]["sessiontoken"]
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self._attr_unique_id = self.coordinator.data[self.idx]["mac"]
        # self._attr_name = self._name

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._mac)
            },
            "name": self._name,
            "manufacturer": "SAL - Pixie Plus",
            "model": "SWL600BTAM",
            "via_device": (DOMAIN, "Pixie Plus Hub"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self._state = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    # @property
    # def brightness(self):
    #    """Return the brightness of the light.
    #   This method is optional. Removing it indicates to Home Assistant
    #    that brightness is not supported for this light.
    #    """
    #    return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Instructs the light to turn on.

        # self._light.brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        await pixiepluslogin.change_light(self, "on")

        # assumes success - will get a push update after few second and will adjust according to the real state
        self.coordinator.data[self.idx]["state"] = "True"
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        await pixiepluslogin.change_light(self, "off")

        self.coordinator.data[self.idx]["state"] = ""
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # await self.coordinator.async_request_refresh()
