"""The pixie_plus integration."""
from __future__ import annotations

# from homeassistant.config_entries import ConfigEntry
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

# from homeassistant.components.light import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from homeassistant.helpers.typing import ConfigType

import asyncio
from datetime import timedelta

from .const import DOMAIN
import logging
import voluptuous as vol

from . import pixiepluslogin

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
    username = config["email"]
    password = config.get(CONF_PASSWORD)
    applicationid = config["applicationid"]
    installationid = config["installationid"]
    javascriptkey = config["javascriptkey"]

    try:
        devices_list = await pixiepluslogin.pixie_login(
            applicationid, installationid, javascriptkey, username, password
        )
    except ConnectionError:
        raise ConfigEntryNotReady(f"Timed out while connecting to Pixie Plus")
    except Exception:
        raise ConfigEntryAuthFailed(f"Credentials expired for Pixie Plus")

    coordinator = MyCoordinator(hass, devices_list)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if config_entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )

    # await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

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

    def __init__(self, hass, my_api):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Pixie Plus",
            # Polling interval. Will only be polled if there are subscribers.
            # update_interval=timedelta(seconds=30),
        )
        self.my_api = my_api
        self._applicationid = self.my_api[0]["applicationid"]
        self._installationid = self.my_api[0]["installationid"]
        self._javascriptkey = self.my_api[0]["javascriptkey"]
        self._sessiontoken = self.my_api[0]["sessiontoken"]
        self._userid = self.my_api[0]["userid"]
        self._homeid = self.my_api[0]["homeid"]
        self.livegroup_objectid = self.my_api[0]["livegroup_objectid"]
        self.platforms = []

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


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
