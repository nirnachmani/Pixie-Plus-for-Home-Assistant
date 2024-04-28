"""The pixie_plus integration."""

from __future__ import annotations

import asyncio

# from datetime import timedelta
import logging

import voluptuous as vol

# from homeassistant.config_entries import ConfigEntry
from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

# from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
# from homeassistant.components.light import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import pixiepluslogin
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.COVER,
]

CONF_COVER_COMMAND = "command"
CONF_COVER_TIME = "time"
CONF_COVER = "cover"
CONF_OPEN = "open"
CONF_CLOSE = "close"
CONF_COVER_STOP = "stop"

# Validation of cover configuration from configuration.yaml

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPEN): cv.positive_int,
        vol.Optional(CONF_CLOSE): cv.positive_int,
        vol.Optional(CONF_COVER_STOP): cv.positive_int,
    }
)

COVER_SCHEMA = vol.Schema(
    {vol.Optional(CONF_COVER): vol.Schema({cv.string: COMMAND_SCHEMA})},
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: COVER_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
) -> bool:
    """Set up pixie_plus from a config entry."""

    config = config_entry.data

    (devices_list, session_data) = await pixiepluslogin.pixie_login(config)

    coordinator = MyCoordinator(hass, config, session_data, devices_list)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if config_entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )

    # await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # calling websocket connection to get push updates
    asyncio.create_task(
        pixiepluslogin.pixie_websocket_connect(config, session_data, coordinator)
    )

    return True


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Pixie Plus Cover component from configuration.yaml"""

    if DOMAIN not in config:  # in case there is no cover device
        config[DOMAIN] = {}

    hass.data[DOMAIN] = config[DOMAIN]

    # hass.helpers.discovery.load_platform("cover", DOMAIN, {}, config)

    return True


class MyCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, config, session_data, devices_list):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Pixie Plus",
            # Polling interval. Will only be polled if there are subscribers.
            # update_interval=timedelta(seconds=30),
        )
        self.config = config
        self.session_data = session_data
        self.devices_list = devices_list
        self.platforms = []

    async def _async_update_data(self):
        self.devices_list = await pixiepluslogin.getdevices(
            self.config, self.session_data
        )
        return self.devices_list


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
