"""Platform for Pixie Plus light integration."""
from __future__ import annotations


import logging

import time

import async_timeout

from . import pixiepluslogin

import asyncio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ATTR_RGB_COLOR,
    ATTR_WHITE,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
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

from .const import (
    DOMAIN,
    hardware_list,
    has_dimming,
    has_color,
    has_white,
    supported_features,
    effect_list,
    is_light,
    is_switch,
    is_cover,
)

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

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # can the above be coordinator = config_entry.data

    # adding entities
    async_add_entities(
        PixiePlusLight(coordinator, idx)
        for idx, ent in enumerate(coordinator.data)
        if ((str(ent["type"]).zfill(2) + str(ent["stype"]).zfill(2)) in is_light)
        or (
            ((str(ent["type"]).zfill(2) + str(ent["stype"]).zfill(2)) not in is_light)
            and (
                str(ent["type"]).zfill(2) + str(ent["stype"]).zfill(2) not in is_switch
            )
            and (str(ent["type"]).zfill(2) + str(ent["stype"]).zfill(2) not in is_cover)
        )
    )


class PixiePlusLight(CoordinatorEntity, LightEntity):
    """Representation of a Pixie Plus Light."""

    def __init__(self, coordinator, idx):

        """Initialize a Pixie Plus Light."""

        super().__init__(coordinator)
        self.idx = idx
        self._name = self.coordinator.data[self.idx]["name"]
        self._mac = self.coordinator.data[self.idx]["mac"]
        self._id = self.coordinator.data[self.idx]["id"]
        self._state = self.coordinator.data[self.idx]["state"]
        self._type = self.coordinator.data[self.idx]["type"]
        self._stype = self.coordinator.data[self.idx]["stype"]
        self._br = self.coordinator.data[self.idx]["br"]
        self._applicationid = self.coordinator.data[self.idx]["applicationid"]
        self._installationid = self.coordinator.data[self.idx]["installationid"]
        self._javascriptkey = self.coordinator.data[self.idx]["javascriptkey"]
        self._userid = self.coordinator.data[self.idx]["userid"]
        self._homeid = self.coordinator.data[self.idx]["homeid"]
        self._livegroup_objectid = self.coordinator.data[self.idx]["livegroup_objectid"]
        self._sessiontoken = self.coordinator.data[self.idx]["sessiontoken"]
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self._attr_unique_id = self.coordinator.data[self.idx]["mac"]
        self._attr_has_entity_name = True
        self._attr_name = None
        self._model_no = str(self._type).zfill(2) + str(self._stype).zfill(2)
        self._supported_color_modes: set[ColorMode | str] = set()
        self._attr_effect_list = []
        if (self._model_no in has_dimming) and (self._model_no not in has_color):
            self._supported_color_modes.add(ColorMode.BRIGHTNESS)
        if self._model_no in has_dimming:
            self._brightness = round(
                (int(self.coordinator.data[self.idx]["br_cur"]) / 100) * 255
            )
            self._last_brightness = ""
        if self._model_no in has_color:
            self._supported_color_modes.add(ColorMode.RGB)
            self._rgb_color = ()
            self._last_rgb_color = ()
        if self._model_no in has_white:
            self._supported_color_modes.add(ColorMode.WHITE)
            self._white = round(
                (int(self.coordinator.data[self.idx]["br_cur"]) / 100) * 255
            )
        if (self._model_no not in has_dimming) and (self._model_no not in has_color):
            self._supported_color_modes.add(ColorMode.ONOFF)
        if self._model_no in supported_features:
            if "EFFECT" in supported_features[self._model_no]:
                self._attr_supported_features |= LightEntityFeature.EFFECT
            if "FLASH" in supported_features[self._model_no]:
                self._attr_supported_features |= LightEntityFeature.FLASH
            if "TRANSITION" in supported_features[self._model_no]:
                self._attr_supported_features |= LightEntityFeature.TRANSITION
        if self._model_no in effect_list:
            self._attr_effect_list = effect_list[self._model_no]

    @property
    def device_info(self):

        if self._model_no in hardware_list:
            model = hardware_list[self._model_no]
        else:
            model = "Unknown model, assuming is light"
            _LOGGER.warning(
                f"adding unknown device, model no {self._model_no}, assuming is light with on/off functionality"
            )

        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._mac)
            },
            "name": self._name,
            "manufacturer": "SAL - Pixie Plus",
            "model": model,
            "via_device": (DOMAIN, "Pixie Plus Hub"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self._state = self.coordinator.data[self.idx]["state"]
        if self._model_no in has_dimming:
            self._brightness = round(
                (int(self.coordinator.data[self.idx]["br_cur"]) / 100) * 255
            )

        if self._model_no in has_white:
            self._white = round(
                (int(self.coordinator.data[self.idx]["br_cur"]) / 100) * 255
            )
        self.async_write_ha_state()

    '''
    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name
    '''

    @property
    def brightness(self) -> int | None:
        if self._model_no in has_dimming:
            return round((int(self.coordinator.data[self.idx]["br_cur"]) / 100) * 255)
        else:
            return None

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if (self._model_no in has_dimming) and (self._model_no not in has_color):
            return ColorMode.BRIGHTNESS
        elif self._model_no in has_color:
            return ColorMode.RGB
        else:
            return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported features."""
        return self._supported_color_modes

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        if self._model_no in has_color:
            return self._rgb_color
        else:
            return None

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Instructs the light to turn on.

        other = {}
        if self._model_no in has_dimming:
            brightness = kwargs.get(ATTR_BRIGHTNESS)
            if brightness:
                self._brightness = brightness
            if (not self._brightness) or (self._brightness == 0):
                if self._last_brightness:
                    self._brightness = self._last_brightness
                else:
                    self._brightness = 255
        if self._model_no in has_color:
            rgb_color = kwargs.get(ATTR_RGB_COLOR)
            if rgb_color:
                self._rgb_color = rgb_color
            elif self._last_rgb_color:
                self._rgb_color = self._last_rgb_color
            other.update({"rgb_color": self._rgb_color})
            if self._model_no in supported_features:
                if "EFFECT" in supported_features[self._model_no]:
                    effect = kwargs.get(ATTR_EFFECT)
                    other.update({"effect": effect})
                if "FLASH" in supported_features[self._model_no]:
                    flash = kwargs.get(ATTR_FLASH)
                    other.update({"flash": flash})
                if "TRANSITION" in supported_features[self._model_no]:
                    transition = kwargs.get(ATTR_TRANSITION)
                    other.update({"transition": transition})
            if self._model_no in has_white:
                white = kwargs.get(ATTR_WHITE)
                other.update({"white": white})
        else:
            other = {}

        if self._model_no in has_dimming:
            brightness_hex = hex(self._brightness)[2:].zfill(2)
        else:
            brightness_hex = "on"

        await pixiepluslogin.change_light(self, brightness_hex, other)

        # assumes success - will get a push update after few second and will adjust according to the real state
        self.coordinator.data[self.idx]["state"] = "True"
        if self._model_no in has_dimming:
            self.coordinator.data[self.idx]["br_cur"] = float(
                (self._brightness / 255) * 100
            )
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        other = {}
        if self._model_no in has_dimming:
            self._last_brightness = self._brightness
        if self._model_no in has_color:
            self._last_rgb_color = self._rgb_color

        await pixiepluslogin.change_light(self, "00", other)

        self.coordinator.data[self.idx]["state"] = ""
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # await self.coordinator.async_request_refresh()
