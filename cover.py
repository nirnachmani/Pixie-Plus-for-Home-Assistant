"""Platform for Pixie Plus switch integration."""

from __future__ import annotations

from datetime import timedelta

import logging

import time
import json

import async_timeout

from . import pixiepluslogin

import asyncio

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
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

from .const import DOMAIN, hardware_list, is_cover, has_two_entities

_LOGGER = logging.getLogger(__name__)

"""
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:

   """


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

    # passing the Pixie Plus devices list with data about all the devices - list of dictionaries, eacy dictionary is a device

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    config = hass.data[DOMAIN]

    cover_exists = 0
    for ent in coordinator.data:
        if (str(ent["type"]).zfill(2) + str(ent["stype"]).zfill(2)) in is_cover:
            cover_exists = 1

    # adding entities
    if cover_exists == 1:
        if (
            "cover" in config
        ):  # checking that user added cover config in configuration.yaml
            cover_config = config["cover"]
            async_add_entities(
                PixiePlusCover(coordinator, idx, cover_config)
                for idx, ent in enumerate(coordinator.data)
                if (str(ent["type"]).zfill(2) + str(ent["stype"]).zfill(2)) in is_cover
            )
        else:
            _LOGGER.error(
                "Unable to add cover entities because they are not defined in configuration.yaml - please see documentation"
            )


class PixiePlusCover(CoordinatorEntity, CoverEntity):
    """Representation of a Pixie Plus Cover."""

    def __init__(self, coordinator, idx, cover_config):
        """Initialize a Pixie Plus Cover."""

        super().__init__(coordinator)
        self.idx = idx
        self._mac = self.coordinator.data[self.idx]["mac"]
        self._id = self.coordinator.data[self.idx]["id"]
        self._type = self.coordinator.data[self.idx]["type"]
        self._stype = self.coordinator.data[self.idx]["stype"]
        self._email = self.coordinator.data[self.idx]["email"]
        self._applicationid = self.coordinator.data[self.idx]["applicationid"]
        self._installationid = self.coordinator.data[self.idx]["installationid"]
        self._clientkey = self.coordinator.data[self.idx]["clientkey"]
        self._userid = self.coordinator.data[self.idx]["userid"]
        self._homeid = self.coordinator.data[self.idx]["homeid"]
        self._livegroup_objectid = self.coordinator.data[self.idx]["livegroup_objectid"]
        self._sessiontoken = self.coordinator.data[self.idx]["sessiontoken"]
        self._attr_has_entity_name = True
        self._model_no = str(self._type).zfill(2) + str(self._stype).zfill(2)
        self._attr_unique_id = self._mac
        self._attr_name = None
        self._cover_name = (
            self.coordinator.data[self.idx]["name"].replace(" ", "_").lower()
        )
        self._attr_supported_features = []
        if self._cover_name in cover_config:
            if "open" in cover_config[self._cover_name]:
                self._cover_open = cover_config[self._cover_name]["open"]
                self._attr_supported_features = CoverEntityFeature.OPEN
            else:
                self._cover_open = ""
            if "close" in cover_config[self._cover_name]:
                self._cover_close = cover_config[self._cover_name]["close"]
                if self._attr_supported_features:
                    self._attr_supported_features |= CoverEntityFeature.CLOSE
                else:
                    self._attr_supported_features = CoverEntityFeature.CLOSE
            else:
                self._cover_close = ""
            if "stop" in cover_config[self._cover_name]:
                self._cover_stop = cover_config[self._cover_name]["stop"]
                if self._attr_supported_features:
                    self._attr_supported_features |= CoverEntityFeature.STOP
                else:
                    self._attr_supported_features = CoverEntityFeature.STOP
            else:
                self._cover_stop = ""
        else:
            _LOGGER.error(
                f"Unable to setup cover {self._cover_name} because there is no matching cover entry in configuration.yaml. See documentation and check spelling or letter case"
            )

        response = pixiepluslogin.initiate_cover(self)
        _LOGGER.debug(
            f"cover after self attribution with following response: {response}"
        )

    @property
    def device_info(self):
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
        return None

    @property
    def is_closed(self):
        return True

    @property
    def assumed_state(self):
        return True

    async def async_open_cover(self, **kwargs: Any) -> None:
        # Instructs the cover to open.

        other = ()
        await pixiepluslogin.change_light(self, "open", other)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to close."""

        other = ()
        await pixiepluslogin.change_light(self, "close", other)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to stop."""

        other = ()
        await pixiepluslogin.change_light(self, "stop", other)
