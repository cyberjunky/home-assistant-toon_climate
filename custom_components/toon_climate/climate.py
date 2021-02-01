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

from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    TEMP_CELSIUS,
)

from homeassistant.helpers.aiohttp_client import async_get_clientsession

import homeassistant.helpers.config_validation as cv

try:
    from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
except ImportError:
    from homeassistant.components.climate import (
        PLATFORM_SCHEMA, 
        ClimateDevice as ClimateEntity,
    )

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

"""
Supported preset modes:

PRESET_AWAY:      The device is in away mode
PRESET_HOME:      The device is in home mode
PRESET_COMFORT:   The device is in comfort mode
PRESET_SLEEP:     The device is in Sleep mode
PRESET_ECO:       The device runs in a continuous energy savings mode. If 
                  configured as one of the supported presets this This mode
                  can be used to activate the vacation mode
"""
SUPPORT_PRESETS = [PRESET_AWAY, PRESET_HOME, PRESET_COMFORT, PRESET_SLEEP, PRESET_ECO]

"""
Supported hvac modes:

- HVAC_MODE_HEAT: Heat to a target temperature (schedule off)
- HVAC_MODE_AUTO: Follow the configured schedule
- HVAC_MODE_OFF:  The device runs in a continuous energy savings mode. If 
                  configured as one of the supported hvac modes this This mode
                  can be used to activate the vacation mode
"""
SUPPORT_MODES = [HVAC_MODE_HEAT, HVAC_MODE_AUTO]

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
        
        """
        Dynamically construct valid preset list
        0: PRESET_COMFORT
        1: PRESET_HOME
        2: PRESET_SLEEP
        3: PRESET_AWAY
        4: PRESET_ECO     
        """
        self._valid_presets = {}
        if (PRESET_COMFORT in SUPPORT_PRESETS): self._valid_presets[0] = PRESET_COMFORT
        if (PRESET_HOME in SUPPORT_PRESETS): self._valid_presets[1] = PRESET_HOME
        if (PRESET_SLEEP in SUPPORT_PRESETS): self._valid_presets[2] = PRESET_SLEEP
        if (PRESET_AWAY in SUPPORT_PRESETS): self._valid_presets[3] = PRESET_AWAY
        if (PRESET_ECO in SUPPORT_PRESETS): self._valid_presets[4] = PRESET_ECO
        
        _LOGGER.info("%s: Supported hvac modes %s. " 
                     "Supported preset modes %s. "
                     "Temperature can be set between %s°C and %s°C", 
                      str(self._name), SUPPORT_MODES, 
                      SUPPORT_PRESETS,
                      self._min_temp, self._max_temp)

    @staticmethod
    async def do_api_request(name, session, url):
        """
        Do an API request
        """
        try:
            with async_timeout.timeout(5):
                response = await session.get(
                    url, headers={"Accept-Encoding": "identity"}
                )
        except aiohttp.ClientError:
            _LOGGER.error("Cannot poll %s using url: %s", name, url)
            return None
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout error occurred while polling %s using url: %s", name, url
            )
            return None

        try:
            response = await response.json(content_type="text/javascript")
            _LOGGER.debug("Data received from %s: %s", name, response)
        except (TypeError, KeyError) as err:
            _LOGGER.error("Cannot parse data received from %s: %s", name, err)
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
            "%s: request 'getThermostatInfo'", str(self._name),
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
            
            if (self._active_state == 4):
                self._hvac_mode = HVAC_MODE_OFF
            elif (self._program_state == 0):
                self._hvac_mode = HVAC_MODE_HEAT
            elif (self._program_state == 1) or (self._program_state == 2):
                self._hvac_mode = HVAC_MODE_AUTO
            else:
                self._hvac_mode = None
   
    @property
    def supported_features(self) -> int:
        """
        Return the list of supported features
        """
        return SUPPORT_FLAGS

    @property
    def name(self) -> str:
        """
        Return the name of the thermostat
        """
        return self._name

    @property
    def temperature_unit(self) -> str:
        """
        Return the unit of measurement (Celcius by default)
        """
        return TEMP_CELSIUS

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
   
        if ((target_temperature < self._min_temp) or 
            (target_temperature > self._max_temp)):
            _LOGGER.warning(
                "%s: set target temperature to %s°C is not supported. "
                "The temperature can be set between %s°C and %s°C", 
                str(self._name), str(target_temperature), 
                self._min_temp, self._max_temp)
            return
   
        _LOGGER.info(
            "%s: set target temperature to %s°C",
            str(self._name), str(target_temperature),
        )

        _LOGGER.debug(
            "%s: request 'setSetpoint' with 'Setpoint' value %s",
            str(self._name), str(value),
        )

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                "/happ_thermstat?action=setSetpoint"
                "&Setpoint=" + str(value),
            ),
        )

        self._current_setpoint = target_temperature

    @property
    def hvac_action(self) -> Optional[str]:
        """
        Return the current running hvac operation

        Toon burnerInfo values
        - 0: Burner is off
        - 1: Burner is on (heating for current setpoint)
        - 2: Burner is on (heating for generating warm water)
        - 3: Burner is on (preheating for next setpoint)
        """
        if (self._burner_info == 1) or (self._burner_info == 3):
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def preset_modes(self) -> List[str]:
        """
        Return the list of available preset modes
        """
        return SUPPORT_PRESETS

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
        try:
            return self._valid_presets[self._active_state]
        except KeyError:
            return None

    async def async_set_preset_mode(self, preset_mode) -> None:
        """
        Set new preset mode (comfort, home, sleep, away, eco)

        Toon programState values
        - 0: Programm mode is off (not automatically changing presets)
        - 1: Programm mode is on (automatically changing presets)
        - 2: Programm mode is on but setpoint/preset is changed until
             the next preset is automatically activated
        - 8: No official programm mode as according to the Toon API doc
             this would be state 4. Testing reveiled it only works when we
             use an 8. This results in the programm state to return back to
             it's original state when another preset is selected.

        Toon activeState values
        - 0: Comfort
        - 1: Home
        - 2: Sleep
        - 3: Away
        - 4: Vacation (eco)
             
        The preset will only be set if it is part of the SUPPORT_PRESETS list
        """
        if not(preset_mode.lower() in SUPPORT_PRESETS):
            _LOGGER.warning(
                "%s: set preset mode to '%s' is not supported. " 
                "Supported preset modes are %s", 
                str(self._name), str(preset_mode.lower()), SUPPORT_PRESETS)
            return None
        
        if preset_mode.lower() == PRESET_COMFORT:
            scheme_temp = 0
            scheme_state = 2
        elif preset_mode.lower() == PRESET_HOME:
            scheme_temp = 1
            scheme_state = 2
        elif preset_mode.lower() == PRESET_SLEEP:
            scheme_temp = 2
            scheme_state = 2
        elif preset_mode.lower() == PRESET_AWAY:
            scheme_temp = 3
            scheme_state = 2
        elif preset_mode.lower() == PRESET_ECO:
            scheme_temp = 4
            scheme_state = 8
        else:
            scheme_temp = -1
            scheme_state = 2

        _LOGGER.info(
            "%s: set preset mode to '%s'",
            str(self._name), str(preset_mode.lower()),
        )    

        _LOGGER.debug(
            "%s: request 'changeSchemeState' with 'state' value %s "
            "and 'temperatureState' value %s",
            str(self._name), str(scheme_state),
            str(scheme_temp),
        )

        self._data = await self.do_api_request(
            self._name, self._session,
            BASE_URL.format(
                self._host, self._port,
                "/happ_thermstat?action=changeSchemeState"
                "&state=" + str(scheme_state) +
                "&temperatureState=" + str(scheme_temp),
            ),
        )

    @property
    def hvac_modes(self) -> List[str]:
        """
        Return the list of available hvac operation modes
        """
        return SUPPORT_MODES

    @property
    def hvac_mode(self) -> Optional[str]:
        """
        Return the current operation mode
        """
        return self._hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """
        Set new target hvac mode

        Support modes:
        - HVAC_MODE_HEAT: Heat to a target temperature (schedule off)
        - HVAC_MODE_AUTO: Follow the configured schedule
        - HVAC_MODE_OFF: Vacation mode (heat to a target architecture)
        
        The hvac mode will only be set if it is part of the SUPPORT_MODES list
        """
        if not(str(hvac_mode) in SUPPORT_MODES):
            _LOGGER.warning(
                "%s: set hvac mode to '%s' is not supported. " 
                "Supported hvac modes are %s", 
                str(self._name), str(hvac_mode), SUPPORT_MODES)
            return None
        
        _LOGGER.info("%s: set hvac mode to '%s'", str(self._name), str(hvac_mode))
      
        if (hvac_mode == HVAC_MODE_HEAT) and (self._active_state == 4):
            """ Set preset to home when returning from vacation """
            _LOGGER.debug(
                "%s: request 'changeSchemeState' with 'state' value %s "
                "and 'temperatureState' value %s",
                str(self._name), str(0), str(1),
            )
            self._data = await self.do_api_request(
                self._name, self._session,
                BASE_URL.format(
                    self._host, self._port,
                    "/happ_thermstat?action=changeSchemeState"
                    "&state=0"
                    "&temperatureState=1",                
                ),
            )
        elif (hvac_mode == HVAC_MODE_HEAT):
            """ No preset needs to be defined """
            _LOGGER.debug(
                "%s: request 'changeSchemeState' with 'state' value %s ",
                str(self._name), str(0)
            )
            self._data = await self.do_api_request(
                self._name, self._session,
                BASE_URL.format(
                    self._host, self._port,
                    "/happ_thermstat?action=changeSchemeState"
                    "&state=0",
                ),
             )   
        elif (hvac_mode == HVAC_MODE_AUTO):
            """ No preset needs to be defined """
            _LOGGER.debug(
                "%s: request 'changeSchemeState' with 'state' value %s ",
                str(self._name), str(1)
            )
            self._data = await self.do_api_request(
                self._name, self._session,
                BASE_URL.format(
                    self._host, self._port,
                    "/happ_thermstat?action=changeSchemeState"
                    "&state=1",
                ),
            )
        elif (hvac_mode == HVAC_MODE_OFF):
            """
            For vacation mode the state needs to be set to 8 
            and the temperature preset needs to be set to 4 
            """
            _LOGGER.debug(
                "%s: request 'changeSchemeState' with 'state' value %s "
                "and 'temperatureState' value %s",
                str(self._name), str(8), str(4),
            )
            self._data = await self.do_api_request(
                self._name, self._session,
                BASE_URL.format(
                    self._host, self._port,
                    "/happ_thermstat?action=changeSchemeState"
                    "&state=8"
                    "&temperatureState=4",                
                ),
            )

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """
        Return additional Toon Thermostat status details

        The information will be available in Home Assistant for reporting
        or automations based on teh provided information
        """
        return {
            "burner_info": self._burner_info,
            "modulation_level": self._modulation_level,
        }
