"""Config flow for Envisalink_new integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_TIMEOUT,
)

from .const import (
    CONF_ALARM_NAME,
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_EVL_KEEPALIVE,
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_NUM_PARTITIONS,
    CONF_NUM_ZONES,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PASS,
    CONF_USERNAME,
    CONF_ZONEDUMP_INTERVAL,
    DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
    DEFAULT_EVL_VERSION,
    DEFAULT_KEEPALIVE,
    DEFAULT_PANIC,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONEDUMP_INTERVAL,
    DEFAULT_ZONETYPE,
    DOMAIN,
    EVL_MAX_PARTITIONS,
    EVL_MAX_ZONES,
    LOGGER,
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
)

from .pyenvisalink import EnvisalinkAlarmPanel

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ALARM_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_EVL_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASS): cv.string,

        vol.Required(CONF_EVL_VERSION, default=DEFAULT_EVL_VERSION): vol.All(
            vol.Coerce(int), vol.In([3, 4])
        ),

        vol.Required(CONF_PANEL_TYPE): vol.All(
            cv.string, vol.In([PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL])
        ),

        vol.Required(CONF_NUM_ZONES, default=EVL_MAX_ZONES) : vol.All(
            vol.Coerce(int), vol.Range(min=1, max=EVL_MAX_ZONES)
        ),
        vol.Required(CONF_NUM_PARTITIONS, default=EVL_MAX_PARTITIONS) : vol.All(
            vol.Coerce(int), vol.Range(min=1, max=EVL_MAX_PARTITIONS)
        ),
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    panel = EnvisalinkAlarmPanel(
        data[CONF_HOST],
        userName=data[CONF_USERNAME],
        password=data[CONF_PASS])

    result = await panel.validate_device_connection()
    if result == EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED:
        raise CannotConnect()
    if result == EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION:
        raise InvalidAuth()

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_ALARM_NAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Envisalink_new."""

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
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception: %r", ex)
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CODE,
                    description={"suggested_value": self.config_entry.options.get(CONF_CODE)}
                ): cv.string,
                vol.Optional(
                    CONF_PANIC,
                    default=self.config_entry.options.get(CONF_PANIC, DEFAULT_PANIC)
                ): cv.string,
                vol.Optional(
                    CONF_EVL_KEEPALIVE,
                    default=self.config_entry.options.get(CONF_EVL_KEEPALIVE, DEFAULT_KEEPALIVE)
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=15)
                ),
                vol.Optional(
                    CONF_ZONEDUMP_INTERVAL,
                    default=self.config_entry.options.get(CONF_ZONEDUMP_INTERVAL, DEFAULT_ZONEDUMP_INTERVAL)
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_TIMEOUT,
                    default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_CREATE_ZONE_BYPASS_SWITCHES,
                    default=self.config_entry.options.get(CONF_CREATE_ZONE_BYPASS_SWITCHES, DEFAULT_CREATE_ZONE_BYPASS_SWITCHES)
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""