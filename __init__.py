"""The pixie_plus integration."""
from __future__ import annotations

# from homeassistant.config_entries import ConfigEntry
from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.components.light import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)


from .const import DOMAIN
import logging
import voluptuous as vol

from . import pixiepluslogin

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]

CONF_EMAIL = "email"
CONF_APPLICATIONID = "applicationid"
CONF_INSTALLATIONID = "installationid"
CONF_JAVASCRIPTKEY = "javascriptkey"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_APPLICATIONID): cv.string,
        vol.Required(CONF_INSTALLATIONID): cv.string,
        vol.Required(CONF_JAVASCRIPTKEY): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up pixie_plus from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.data

    config = hass.data[DOMAIN][config_entry.entry_id]
    username = config[CONF_EMAIL]
    password = config.get(CONF_PASSWORD)
    applicationid = config[CONF_APPLICATIONID]
    installationid = config[CONF_INSTALLATIONID]
    javascriptkey = config[CONF_JAVASCRIPTKEY]

    try:
        devices_list = await pixiepluslogin.pixie_login(
            applicationid, installationid, javascriptkey, username, password
        )
    except ConnectionError:
        raise ConfigEntryNotReady(f"Timed out while connecting to Pixie Plus")
    except Exception:
        raise ConfigEntryAuthFailed(f"Credentials expired for Pixie Plus")

    hass.data[DOMAIN][config_entry.entry_id] = devices_list

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
