"""Config flow for pixie_plus integration."""
from __future__ import annotations

from . import pixiepluslogin

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("email"): str,
        vol.Required("password"): str,
        vol.Required("applicationid"): str,
        vol.Required("installationid"): str,
        vol.Required("javascriptkey"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # If your PyPI package is not built with async, pass your methods
    # to the executor:

    api_url = {
        "userquery": "https://www.pixie.app/p0/pixieCloud/functions/userQuery",
        "login": "https://www.pixie.app/p0/pixieCloud/login",
    }

    if not await hass.async_add_executor_job(pixiepluslogin.check_user, api_url, data):
        raise InvalidAuth

    if (
        await hass.async_add_executor_job(pixiepluslogin.login, api_url, data)
        == "LoginError"
    ):
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {
        "email": data["email"],
        "password": data["password"],
        "applicationid": data["applicationid"],
        "installationid": data["installationid"],
        "javascriptkey": data["javascriptkey"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pixie_plus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="Pixie Plus", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
