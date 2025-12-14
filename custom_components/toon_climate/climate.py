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
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """
    Setup the Toon thermostat
    """
    session = async_get_clientsession(hass)
    async_add_entities([ThermostatDevice(session, config)], update_before_add=True)

class ThermostatDevice(ClimateEntity):
    """
    Representation of a Toon climate device
    """

    def __init__(self, session: aiohttp.ClientSession, config: ConfigType) -> None:
        """
        Initialize the Toon climate device
        """
        self._session = session
        self._name = config.get(CONF_NAME, DEFAULT_NAME)
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT, 80)
        self._min_temp = max(
            config.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
            DEFAULT_MIN_TEMP
        )
        self._max_temp = min(
            config.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
            DEFAULT_MAX_TEMP
        )
        self._attr_unique_id = f"climate_{self._name}_{self._host}"
        self._attr_name = self._name
        self._attr_hvac_modes = SUPPORT_MODES
        self._attr_preset_modes = SUPPORT_PRESETS
        self._attr_supported_features = SUPPORT_FLAGS
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        """
        Standard thermostat data for the first and second edition of Toon
        """
        self._data: dict[str, Any] | None = None
        self._active_state: int | None = None
        self._burner_info: int | None = None
        self._modulation_level: int | None = None
        self._current_setpoint: float | None = None
        self._current_temperature: float | None = None
        self._ot_comm_error: int | None = None
        self._program_state: int | None = None
        self._attr_hvac_mode: HVACMode | None = None
        self._attr_current_temperature: float | None = None
        self._attr_target_temperature: float | None = None
        self._attr_preset_mode: str | None = None

        _LOGGER.info("%s: Supported hvac modes %s. "
                     "Supported preset modes %s. "
                     "Temperature can be set between %s°C and %s°C",
                     self._name, SUPPORT_MODES,
                     SUPPORT_PRESETS,
                     self._min_temp, self._max_temp)

    @staticmethod
    async def do_api_request(name: str, session: aiohttp.ClientSession, url: str) -> dict[str, Any] | None:
        """
        Do an API request
        """
        try:
            async with asyncio.timeout(5):
                response = await session.get(
                    url, headers={"Accept-Encoding": "identity"}
                )
            response = await response.json(content_type="text/javascript")
            _LOGGER.debug("Data received from %s: %s",
                          name, response)
        except (aiohttp.ClientError, TimeoutError, TypeError, KeyError) as err:
            _LOGGER.error("Cannot poll %s using url: %s - %s",
                          name, url, err)
            return None

        return response

    @property
    def should_poll(self) -> bool:
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

            # Update entity attributes
            self._attr_target_temperature = self._current_setpoint
            self._attr_current_temperature = self._current_temperature

            # Determine HVAC mode based on program_state
            # Note: active_state 4 (vacation/eco) is a preset, not an HVAC mode
            # The HVAC mode should still be determined from program_state
            if self._program_state == 0:
                self._attr_hvac_mode = HVACMode.HEAT
            elif self._program_state in (1, 2):
                self._attr_hvac_mode = HVACMode.AUTO
            else:
                # Default to AUTO if program_state is unknown
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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """
        Set target temperature
        """
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return

        value = int(target_temperature * 100)

        if target_temperature < self._min_temp or target_temperature > self._max_temp:
            _LOGGER.warning(
                "%s: set target temperature to %s°C is not supported. "
                "The temperature can be set between %s°C and %s°C",
                self._name, target_temperature,
                self._min_temp, self._max_temp)
            return

        _LOGGER.info(
            "%s: set target temperature to %s°C",
            self._name, target_temperature,
        )

        _LOGGER.debug(
            "%s: request 'setSetpoint' with 'Setpoint' value %s",
            self._name, value,
        )

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                f"/happ_thermstat?action=setSetpoint&Setpoint={value}",
            ),
        )

        if self._data:
            self._current_setpoint = target_temperature
            self._attr_target_temperature = target_temperature

    @property
    def hvac_action(self) -> HVACAction | None:
        """
        Return the current running hvac operation

        Toon burnerInfo values
        - 0: Burner is off
        - 1: Burner is on (heating for current setpoint)
        - 2: Burner is on (heating for generating warm water)
        - 3: Burner is on (preheating for next setpoint)
        """
        if self._burner_info in (1, 3):
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
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

        _LOGGER.info(
            "%s: set preset mode to '%s'",
            self._name, preset_lower,
        )

        _LOGGER.debug(
            "%s: request 'changeSchemeState' with 'state' value %s "
            "and 'temperatureState' value %s",
            self._name, scheme_state,
            scheme_temp,
        )

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                f"/happ_thermstat?action=changeSchemeState&state={scheme_state}&temperatureState={scheme_temp}",
            ),
        )

        if self._data:
            self._attr_preset_mode = preset_lower

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """
        Set new target hvac mode
        """
        if hvac_mode not in SUPPORT_MODES:
            _LOGGER.warning(
                "%s: set hvac mode to '%s' is not supported. "
                "Supported hvac modes are %s",
                self._name, hvac_mode, SUPPORT_MODES)
            return

        _LOGGER.info("%s: set hvac mode to '%s'", self._name, hvac_mode)

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
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                url,
            ),
        )

        if self._data:
            self._attr_hvac_mode = hvac_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return additional Toon Thermostat status details
        """
        return {
            "burner_info": self._burner_info,
            "modulation_level": self._modulation_level,
            "ot_comm_error": self._ot_comm_error,
            "program_state": self._program_state,
        }
