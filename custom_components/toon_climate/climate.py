"""
Climate support for Toon thermostat.
Only for the rooted version.

configuration.yaml

climate:
  - platform: toon_climate
    name: Toon Thermostat
    host: <IP_ADDRESS>
    port: 80
    scan_interval: 10
    min_temp: 6.0
    max_temp: 30.0

logger:
  default: info
  logs:
    custom_components.toon_climate: debug

More details:
- https://developers.home-assistant.io/docs/core/entity/climate/
- https://github.com/cyberjunky/home-assistant-toon_climate
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    UnitOfTemperature,
)

from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE | 
    ClimateEntityFeature.PRESET_MODE
)

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

DEFAULT_NAME = "Toon Thermostat"
BASE_URL = "http://{0}:{1}{2}"

"""
The Toon device can be set to a minumum of 6 degrees celsius and a maximum
of 30 degrees celsius. The below min and max values should not be changed.
"""
DEFAULT_MIN_TEMP = 6.0
DEFAULT_MAX_TEMP = 30.0
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.positive_int,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    }
)

async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """
    Setup the Toon thermostat
    """
    session = async_get_clientsession(hass)
    add_devices([ThermostatDevice(session, config)], True)

class ThermostatDevice(ClimateEntity):
    """
    Representation of a Toon climate device
    """

    def __init__(self, session, config) -> None:
        """
        Initialize the Toon climate device
        """
        self._session = session
        self._name = config.get(CONF_NAME)
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._min_temp = (config.get(CONF_MIN_TEMP)
                          if config.get(CONF_MIN_TEMP) >= DEFAULT_MIN_TEMP
                          else DEFAULT_MIN_TEMP)
        self._max_temp = (config.get(CONF_MAX_TEMP)
                          if config.get(CONF_MAX_TEMP) <= DEFAULT_MAX_TEMP
                          else DEFAULT_MAX_TEMP)
        self._attr_unique_id = f"climate_{self._name}_{self._host}"
        self._attr_hvac_modes = SUPPORT_MODES
        self._attr_preset_modes = SUPPORT_PRESETS
        self._attr_supported_features = SUPPORT_FLAGS
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        """
        Standard thermostat data for the first and second edition of Toon
        """
        self._data = None
        self._active_state = None
        self._burner_info = None
        self._modulation_level = None
        self._current_setpoint = None
        self._current_temperature = None
        self._ot_comm_error = None
        self._program_state = None
        self._hvac_mode = None

        _LOGGER.info("%s: Supported hvac modes %s. "
                     "Supported preset modes %s. "
                     "Temperature can be set between %s°C and %s°C",
                     self._name, SUPPORT_MODES,
                     SUPPORT_PRESETS,
                     self._min_temp, self._max_temp)

    @staticmethod
    async def do_api_request(name, session, url):
        """
        Do an API request
        """
        try:
            async with async_timeout.timeout(5):
                response = await session.get(
                    url, headers={"Accept-Encoding": "identity"}
                )
            response = await response.json(content_type="text/javascript")
            _LOGGER.debug("Data received from %s: %s",
                          name, response)
        except (aiohttp.ClientError, asyncio.TimeoutError, TypeError, KeyError) as err:
            _LOGGER.error("Cannot poll %s using url: %s - %s",
                          name, url, err)
            return None

        return response

    @property
    def should_poll(self):
        """
        Polling needed for thermostat
        """
        return True

    async def async_update(self) -> None:
        """
        Update local data with thermostat data (Toon 1 and Toon 2)
        """
        _LOGGER.debug(
            "%s: request 'getThermostatInfo'", self._name,
        )

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                "/happ_thermstat?action=getThermostatInfo"
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

            if self._active_state == 4:
                self._hvac_mode = HVACMode.OFF
            elif self._program_state == 0:
                self._hvac_mode = HVACMode.HEAT
            elif self._program_state == 1 or self._program_state == 2:
                self._hvac_mode = HVACMode.AUTO
            else:
                self._hvac_mode = None

            self._attr_hvac_mode = self._hvac_mode

    @property
    def name(self) -> str:
        """
        Return the name of the thermostat
        """
        return self._name

    @property
    def min_temp(self) -> float:
        """
        Return the minimum temperature
        """
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """
        Return the maximum temperature
        """
        return self._max_temp

    @property
    def current_temperature(self) -> Optional[float]:
        """
        Return the current temperature
        """
        return self._current_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """
        Return current target temperature (temp we try to reach)
        """
        return self._current_setpoint

    async def async_set_temperature(self, **kwargs) -> None:
        """
        Set target temperature
        """
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return

        value = int(target_temperature * 100)

        if (target_temperature < self._min_temp or
                target_temperature > self._max_temp):
            _LOGGER.warning(
                "%s: set target temperature to %s°C is not supported. "
                "The temperature can be set between %s°C and %s°C",
                self._name, str(target_temperature),
                self._min_temp, self._max_temp)
            return

        _LOGGER.info(
            "%s: set target temperature to %s°C",
            self._name, str(target_temperature),
        )

        _LOGGER.debug(
            "%s: request 'setSetpoint' with 'Setpoint' value %s",
            self._name, str(value),
        )

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                f"/happ_thermstat?action=setSetpoint&Setpoint={value}",
            ),
        )

        self._current_setpoint = target_temperature

    @property
    def hvac_action(self) -> Optional[HVACAction]:
        """
        Return the current running hvac operation

        Toon burnerInfo values
        - 0: Burner is off
        - 1: Burner is on (heating for current setpoint)
        - 2: Burner is on (heating for generating warm water)
        - 3: Burner is on (preheating for next setpoint)
        """
        if (self._burner_info == 1) or (self._burner_info == 3):
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> Optional[str]:
        """
        Return the current preset mode

        Toon activeState values
        - 0: Comfort
        - 1: Home
        - 2: Sleep
        - 3: Away
        - 4: Vacation (not a default home assistant climate state) instead we
             use the PRESET_ECO if configured as one of the supported presets
        """
        mapping = {
            0: PRESET_COMFORT,
            1: PRESET_HOME,
            2: PRESET_SLEEP,
            3: PRESET_AWAY,
            4: PRESET_ECO
        }
        return mapping.get(self._active_state)

    async def async_set_preset_mode(self, preset_mode) -> None:
        """
        Set new preset mode (comfort, home, sleep, away, eco)
        """
        preset_lower = preset_mode.lower()
        if preset_lower not in SUPPORT_PRESETS:
            _LOGGER.warning(
                "%s: set preset mode to '%s' is not supported. "
                "Supported preset modes are %s",
                self._name, preset_lower, SUPPORT_PRESETS)
            return

        if preset_lower == PRESET_COMFORT:
            scheme_temp = 0
            scheme_state = 2
        elif preset_lower == PRESET_HOME:
            scheme_temp = 1
            scheme_state = 2
        elif preset_lower == PRESET_SLEEP:
            scheme_temp = 2
            scheme_state = 2
        elif preset_lower == PRESET_AWAY:
            scheme_temp = 3
            scheme_state = 2
        elif preset_lower == PRESET_ECO:
            scheme_temp = 4
            scheme_state = 8
        else:
            return

        _LOGGER.info(
            "%s: set preset mode to '%s'",
            self._name, preset_lower,
        )

        _LOGGER.debug(
            "%s: request 'changeSchemeState' with 'state' value %s "
            "and 'temperatureState' value %s",
            self._name, str(scheme_state),
            str(scheme_temp),
        )

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                f"/happ_thermstat?action=changeSchemeState&state={scheme_state}&temperatureState={scheme_temp}",
            ),
        )

    @property
    def hvac_mode(self) -> Optional[str]:
        """
        Return the current operation mode
        """
        return self._hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """
        Set new target hvac mode
        """
        if hvac_mode not in SUPPORT_MODES:
            _LOGGER.warning(
                "%s: set hvac mode to '%s' is not supported. "
                "Supported hvac modes are %s",
                self._name, str(hvac_mode), SUPPORT_MODES)
            return

        _LOGGER.info("%s: set hvac mode to '%s'", self._name, str(hvac_mode))

        if hvac_mode == HVACMode.HEAT:
            if self._active_state == 4:
                url = f"/happ_thermstat?action=changeSchemeState&state=0&temperatureState=1"
            else:
                url = "/happ_thermstat?action=changeSchemeState&state=0"
        elif hvac_mode == HVACMode.AUTO:
            url = "/happ_thermstat?action=changeSchemeState&state=1"
        else:
            return

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                url,
            ),
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """
        Return additional Toon Thermostat status details
        """
        return {
            "burner_info": self._burner_info,
            "modulation_level": self._modulation_level,
        }
