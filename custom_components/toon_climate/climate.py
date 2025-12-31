"""Climate support for Toon thermostat.

Only for the rooted version.

More details:
- https://developers.home-assistant.io/docs/core/entity/climate/
- https://github.com/cyberjunky/home-assistant-toon_climate
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

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

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

"""
Supported preset modes:

PRESET_AWAY:      The device is in away mode
PRESET_HOME:      The device is in home mode
PRESET_COMFORT:   The device is in comfort mode
PRESET_SLEEP:     The device is in Sleep mode
PRESET_ECO:       The device runs in a continuous energy savings mode. If
                  configured as one of the supported presets this mode can
                  be used to activate the vacation mode
"""
SUPPORT_PRESETS = [PRESET_AWAY, PRESET_HOME, PRESET_COMFORT, PRESET_SLEEP, PRESET_ECO]

"""
Supported hvac modes:

- HVACMode.HEAT: Heat to a target temperature (schedule off)
- HVACMode.AUTO: Follow the configured schedule
"""
SUPPORT_MODES = [HVACMode.HEAT, HVACMode.AUTO]

BASE_URL = "http://{0}:{1}{2}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Toon Climate platform from a config entry."""
    session = async_get_clientsession(hass)
    
    # Get scan interval from options
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
    entity = ThermostatDevice(session, entry, scan_interval)
    async_add_entities([entity], update_before_add=True)


class ThermostatDevice(ClimateEntity):
    """Representation of a Toon climate device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False  # We handle our own polling

    def __init__(self, session: aiohttp.ClientSession, entry: ConfigEntry, scan_interval: int) -> None:
        """Initialize the Toon climate device."""
        self._session = session
        self._entry = entry
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_update: callable | None = None

        # Get configuration from entry data and options
        self._host = entry.data.get(CONF_HOST)
        self._port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._device_name = entry.data.get(CONF_NAME, DEFAULT_NAME)

        # Temperature limits from options (with fallback to defaults)
        self._min_temp = max(entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP), DEFAULT_MIN_TEMP)
        self._max_temp = min(entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP), DEFAULT_MAX_TEMP)

        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_hvac_modes = SUPPORT_MODES
        self._attr_preset_modes = SUPPORT_PRESETS
        self._attr_supported_features = SUPPORT_FLAGS
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=self._device_name,
            manufacturer="Eneco",
            model="Toon Thermostat",
            configuration_url=f"http://{self._host}:{self._port}",
        )

        # Thermostat data
        self._data: dict[str, Any] | None = None
        self._active_state: int | None = None
        self._burner_info: int | None = None
        self._modulation_level: int | None = None
        self._current_internal_boiler_setpoint: int | None = None
        self._current_setpoint: float | None = None
        self._current_temperature: float | None = None
        self._ot_comm_error: int | None = None
        self._program_state: int | None = None
        self._attr_hvac_mode: HVACMode | None = None
        self._attr_current_temperature: float | None = None
        self._attr_target_temperature: float | None = None
        self._attr_preset_mode: str | None = None

        _LOGGER.info(
            "%s: Supported hvac modes %s. "
            "Supported preset modes %s. "
            "Temperature can be set between %s°C and %s°C. "
            "Update interval: %s seconds",
            self._device_name,
            SUPPORT_MODES,
            SUPPORT_PRESETS,
            self._min_temp,
            self._max_temp,
            scan_interval,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # Do initial update
        await self._async_update_data()
        
        # Set up periodic updates
        self._unsub_update = async_track_time_interval(
            self.hass,
            self._async_scheduled_update,
            self._scan_interval,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is being removed from hass."""
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

    @callback
    def _async_scheduled_update(self, now=None) -> None:
        """Handle scheduled update."""
        self.hass.async_create_task(self._async_update_data())

    async def _async_update_data(self) -> None:
        """Fetch data from the thermostat."""
        _LOGGER.debug("%s: request 'getThermostatInfo'", self._device_name)

        self._data = await self.do_api_request(
            self._device_name,
            self._session,
            BASE_URL.format(
                self._host,
                self._port,
                "/happ_thermstat?action=getThermostatInfo",
            ),
        )

        if self._data:
            self._active_state = int(self._data["activeState"])
            self._burner_info = int(self._data["burnerInfo"])
            self._modulation_level = int(self._data["currentModulationLevel"])
            self._current_setpoint = int(self._data["currentSetpoint"]) / 100
            self._current_temperature = int(self._data["currentTemp"]) / 100
            self._ot_comm_error = int(self._data["otCommError"])
            self._program_state = int(self._data["programState"])

            # Update entity attributes
            self._attr_target_temperature = self._current_setpoint
            self._attr_current_temperature = self._current_temperature

            # Determine HVAC mode based on program_state
            if self._program_state == 0:
                self._attr_hvac_mode = HVACMode.HEAT
            elif self._program_state in (1, 2):
                self._attr_hvac_mode = HVACMode.AUTO
            else:
                self._attr_hvac_mode = HVACMode.AUTO

            # Update preset mode
            preset_mapping = {
                0: PRESET_COMFORT,
                1: PRESET_HOME,
                2: PRESET_SLEEP,
                3: PRESET_AWAY,
                4: PRESET_ECO,
            }
            self._attr_preset_mode = preset_mapping.get(self._active_state)

        # Notify HA that state has changed
        self.async_write_ha_state()

    @staticmethod
    async def do_api_request(
        name: str, session: aiohttp.ClientSession, url: str
    ) -> dict[str, Any] | None:
        """Do an API request."""
        try:
            async with asyncio.timeout(5):
                response = await session.get(url, headers={"Accept-Encoding": "identity"})
            response = await response.json(content_type="text/javascript")
            _LOGGER.debug("Data received from %s: %s", name, response)
        except (aiohttp.ClientError, TimeoutError, TypeError, KeyError) as err:
            _LOGGER.error("Cannot poll %s using url: %s - %s", name, url, err)
            return None

        return response

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temp

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return

        value = int(target_temperature * 100)

        if target_temperature < self._min_temp or target_temperature > self._max_temp:
            _LOGGER.warning(
                "%s: set target temperature to %s°C is not supported. "
                "The temperature can be set between %s°C and %s°C",
                self._device_name,
                target_temperature,
                self._min_temp,
                self._max_temp,
            )
            return

        _LOGGER.info(
            "%s: set target temperature to %s°C",
            self._device_name,
            target_temperature,
        )

        _LOGGER.debug(
            "%s: request 'setSetpoint' with 'Setpoint' value %s",
            self._device_name,
            value,
        )

        self._data = await self.do_api_request(
            self._device_name,
            self._session,
            BASE_URL.format(
                self._host,
                self._port,
                f"/happ_thermstat?action=setSetpoint&Setpoint={value}",
            ),
        )

        if self._data:
            self._current_setpoint = target_temperature
            self._attr_target_temperature = target_temperature

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation.

        Toon burnerInfo values:
        - 0: Burner is off
        - 1: Burner is on (heating for current setpoint)
        - 2: Burner is on (heating for generating warm water)
        - 3: Burner is on (preheating for next setpoint)
        """
        if self._burner_info in (1, 3):
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode (comfort, home, sleep, away, eco)."""
        preset_lower = preset_mode.lower()
        if preset_lower not in SUPPORT_PRESETS:
            _LOGGER.warning(
                "%s: set preset mode to '%s' is not supported. Supported preset modes are %s",
                self._device_name,
                preset_lower,
                SUPPORT_PRESETS,
            )
            return

        preset_mapping = {
            PRESET_COMFORT: (0, 2),
            PRESET_HOME: (1, 2),
            PRESET_SLEEP: (2, 2),
            PRESET_AWAY: (3, 2),
            PRESET_ECO: (4, 8),
        }

        scheme_temp, scheme_state = preset_mapping.get(preset_lower, (None, None))
        if scheme_temp is None:
            return

        _LOGGER.info("%s: set preset mode to '%s'", self._device_name, preset_lower)

        _LOGGER.debug(
            "%s: request 'changeSchemeState' with 'state' value %s and 'temperatureState' value %s",
            self._device_name,
            scheme_state,
            scheme_temp,
        )

        self._data = await self.do_api_request(
            self._device_name,
            self._session,
            BASE_URL.format(
                self._host,
                self._port,
                f"/happ_thermstat?action=changeSchemeState&state={scheme_state}&temperatureState={scheme_temp}",
            ),
        )

        if self._data:
            self._attr_preset_mode = preset_lower

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in SUPPORT_MODES:
            _LOGGER.warning(
                "%s: set hvac mode to '%s' is not supported. Supported hvac modes are %s",
                self._device_name,
                hvac_mode,
                SUPPORT_MODES,
            )
            return

        _LOGGER.info("%s: set hvac mode to '%s'", self._device_name, hvac_mode)

        if hvac_mode == HVACMode.HEAT:
            if self._active_state == 4:
                url = "/happ_thermstat?action=changeSchemeState&state=0&temperatureState=1"
            else:
                url = "/happ_thermstat?action=changeSchemeState&state=0"
        elif hvac_mode == HVACMode.AUTO:
            url = "/happ_thermstat?action=changeSchemeState&state=1"
        else:
            return

        self._data = await self.do_api_request(
            self._device_name,
            self._session,
            BASE_URL.format(self._host, self._port, url),
        )

        if self._data:
            self._attr_hvac_mode = hvac_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional Toon Thermostat status details."""
        return {
            "burner_info": self._burner_info,
            "modulation_level": self._modulation_level,
            "current_internal_boiler_setpoint": self._current_internal_boiler_setpoint,
            "ot_comm_error": self._ot_comm_error,
            "program_state": self._program_state,
        }
