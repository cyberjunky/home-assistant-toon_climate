"""Config flow for Toon Climate integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

BASE_URL = "http://{0}:{1}/happ_thermstat?action=getThermostatInfo"


async def validate_connection(host: str, port: int, session: aiohttp.ClientSession) -> bool:
    """Validate the connection to the Toon device."""
    try:
        async with asyncio.timeout(10):
            url = BASE_URL.format(host, port)
            response = await session.get(url, headers={"Accept-Encoding": "identity"})
            if response.status == 200:
                # Try to parse the response to ensure it's valid JSON
                await response.json(content_type="text/javascript")
                return True
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Connection validation failed: %s", err)
    return False


class ToonClimateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Toon Climate."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            name = user_input.get(CONF_NAME, DEFAULT_NAME)

            # Set unique ID based on host to prevent duplicates
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Validate connection
            session = async_get_clientsession(self.hass)
            if await validate_connection(host, port, session):
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_NAME: name,
                    },
                    options={
                        CONF_MIN_TEMP: user_input.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
                        CONF_MAX_TEMP: user_input.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
                        CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
                    vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(int),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        host = import_data.get(CONF_HOST)
        if not host:
            return self.async_abort(reason="invalid_import")

        # Set unique ID based on host
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        _LOGGER.info("Importing Toon Climate configuration from YAML for host: %s", host)

        return self.async_create_entry(
            title=import_data.get(CONF_NAME, DEFAULT_NAME),
            data={
                CONF_HOST: host,
                CONF_PORT: import_data.get(CONF_PORT, DEFAULT_PORT),
                CONF_NAME: import_data.get(CONF_NAME, DEFAULT_NAME),
            },
            options={
                CONF_MIN_TEMP: import_data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
                CONF_MAX_TEMP: import_data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
                CONF_SCAN_INTERVAL: import_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return ToonClimateOptionsFlowHandler(config_entry)


class ToonClimateOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Toon Climate."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            new_options = {
                CONF_MIN_TEMP: user_input.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
                CONF_MAX_TEMP: user_input.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
                CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            }

            # Update options only (data remains unchanged after initial setup)
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                options=new_options,
            )
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema(),
        )

    def _get_options_schema(self) -> vol.Schema:
        """Return the options schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_MIN_TEMP,
                    default=self._config_entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_MAX_TEMP,
                    default=self._config_entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self._config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.Coerce(int),
            }
        )
