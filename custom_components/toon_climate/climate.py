"""Climate support for Toon thermostat.

Only for the rooted version.

More details:
- https://developers.home-assistant.io/docs/core/entity/climate/
- https://github.com/cyberjunky/home-assistant-toon_climate
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_STATE_HOLIDAY,
    ACTIVE_STATE_HOME,
    ACTIVE_STATE_MANUAL,
    ACTIVE_STATE_TO_PRESET,
    BURNER_HEATING,
    BURNER_PREHEATING,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PRESET_TO_SCHEME,
    PROGRAM_PRESET_STATES,
    PROGRAM_STATE_OFF,
    REQUEST_TIMEOUT,
    SCHEME_STATE_PROGRAM_OFF,
    SCHEME_STATE_PROGRAM_ON,
    SCHEME_STATE_TEMPORARY,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

# Supported preset modes:
#
# PRESET_NONE:    Manual setpoint, no preset active (Toon activeState -1)
# PRESET_AWAY:    The device is in away mode
# PRESET_HOME:    The device is in home mode
# PRESET_COMFORT: The device is in comfort mode
# PRESET_SLEEP:   The device is in sleep mode
# PRESET_ECO:     Vacation mode, a continuous energy saving mode
SUPPORT_PRESETS = [
    PRESET_NONE,
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_COMFORT,
    PRESET_SLEEP,
    PRESET_ECO,
]

# Supported hvac modes:
#
# HVACMode.HEAT: Heat to a target temperature (program off)
# HVACMode.AUTO: Follow the configured program
SUPPORT_MODES = [HVACMode.HEAT, HVACMode.AUTO]

BASE_URL = "http://{0}:{1}{2}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Toon Climate platform from a config entry."""
    session = async_get_clientsession(hass)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    async_add_entities([ThermostatDevice(session, entry, scan_interval)])


class ThermostatDevice(ClimateEntity):
    """Representation of a Toon climate device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False  # We handle our own polling
    _attr_hvac_modes = SUPPORT_MODES
    _attr_preset_modes = SUPPORT_PRESETS
    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, session: aiohttp.ClientSession, entry: ConfigEntry, scan_interval: int
    ) -> None:
        """Initialize the Toon climate device."""
        self._session = session
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_update: CALLBACK_TYPE | None = None

        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._device_name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)

        # Temperature limits from options, clamped to what Toon accepts
        self._attr_min_temp = max(
            entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP), DEFAULT_MIN_TEMP
        )
        self._attr_max_temp = min(
            entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP), DEFAULT_MAX_TEMP
        )

        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=self._device_name,
            manufacturer="Eneco",
            model="Toon Thermostat",
            configuration_url=f"http://{self._host}:{self._port}",
        )

        # Thermostat data
        self._active_state: int | None = None
        self._burner_info: int | None = None
        self._modulation_level: int | None = None
        self._current_internal_boiler_setpoint: int | None = None
        self._current_setpoint: float | None = None
        self._ot_comm_error: int | None = None
        self._program_state: int | None = None
        self._next_setpoint: float | None = None
        self._next_state: int | None = None
        self._next_switch_time: datetime | None = None

        _LOGGER.debug(
            "%s: hvac modes %s, preset modes %s, temperature range %s-%s°C, update interval %ss",
            self._device_name,
            SUPPORT_MODES,
            SUPPORT_PRESETS,
            self._attr_min_temp,
            self._attr_max_temp,
            scan_interval,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await self._async_update_data()
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
    def _async_scheduled_update(self, _now: datetime) -> None:
        """Handle scheduled update."""
        self.hass.async_create_background_task(
            self._async_update_data(), f"{DOMAIN} update {self._device_name}"
        )

    async def _async_request(self, path: str) -> dict[str, Any] | None:
        """Do an API request and return the decoded JSON, or None on failure."""
        url = BASE_URL.format(self._host, self._port, path)
        _LOGGER.debug("%s: request %s", self._device_name, url)
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.get(url, headers={"Accept-Encoding": "identity"})
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("%s: request %s failed: %s", self._device_name, url, err)
            return None

        if not isinstance(data, dict):
            _LOGGER.debug("%s: unexpected response from %s: %s", self._device_name, url, data)
            return None

        _LOGGER.debug("%s: response %s", self._device_name, data)
        return data

    async def _async_send_command(self, path: str) -> None:
        """Send a command to the Toon, raising when it cannot be delivered."""
        data = await self._async_request(path)
        if data is None or data.get("success") is False:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"name": self._device_name, "host": self._host},
            )

    async def _async_update_data(self) -> None:
        """Fetch data from the thermostat and write the new state."""
        data = await self._async_request("/happ_thermstat?action=getThermostatInfo")

        if data is None or not self._parse_thermostat_info(data):
            if self._attr_available:
                _LOGGER.error(
                    "%s: cannot read thermostat info from %s:%s, marking unavailable",
                    self._device_name,
                    self._host,
                    self._port,
                )
            self._attr_available = False
        else:
            if not self._attr_available:
                _LOGGER.info("%s: connection restored", self._device_name)
            self._attr_available = True

        self.async_write_ha_state()

    def _parse_thermostat_info(self, data: dict[str, Any]) -> bool:
        """Parse a getThermostatInfo response into entity state."""
        try:
            self._active_state = int(data["activeState"])
            self._burner_info = int(data["burnerInfo"])
            self._modulation_level = int(data["currentModulationLevel"])
            self._current_setpoint = int(data["currentSetpoint"]) / 100
            self._attr_current_temperature = int(data["currentTemp"]) / 100
            self._current_internal_boiler_setpoint = int(data["currentInternalBoilerSetpoint"])
            self._ot_comm_error = int(data["otCommError"])
            self._program_state = int(data["programState"])
            next_setpoint = int(data.get("nextSetpoint", 0))
            self._next_setpoint = next_setpoint / 100 if next_setpoint else None
            self._next_state = int(data["nextState"]) if "nextState" in data else None
            next_switch_raw = data.get("nextSwitchTime") or data.get("nextTime")
            self._next_switch_time = (
                datetime.fromtimestamp(int(next_switch_raw), tz=UTC) if next_switch_raw else None
            )
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("%s: cannot parse thermostat info %s: %s", self._device_name, data, err)
            return False

        self._attr_target_temperature = self._current_setpoint
        self._attr_hvac_mode = (
            HVACMode.HEAT if self._program_state == PROGRAM_STATE_OFF else HVACMode.AUTO
        )
        self._attr_preset_mode = ACTIVE_STATE_TO_PRESET.get(self._active_state, PRESET_NONE)
        return True

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation.

        Toon burnerInfo values:
        - 0: Burner is off
        - 1: Burner is on (heating for current setpoint)
        - 2: Burner is on (heating for generating warm water)
        - 3: Burner is on (preheating for next setpoint)
        """
        if self._burner_info is None:
            return None
        if self._burner_info in (BURNER_HEATING, BURNER_PREHEATING):
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return

        value = round(target_temperature * 100)
        _LOGGER.debug("%s: set target temperature to %s°C", self._device_name, target_temperature)

        await self._async_send_command(f"/happ_thermstat?action=setSetpoint&Setpoint={value}")
        await self._async_update_data()

        # Toon only recognises some preset temperatures as that preset
        if (
            self._attr_available
            and self._program_state != PROGRAM_STATE_OFF
            and self._active_state == ACTIVE_STATE_MANUAL
        ):
            await self._async_activate_matching_preset(value)

    async def _async_activate_matching_preset(self, setpoint: int) -> None:
        """Temporarily activate the preset whose temperature is setpoint."""
        data = await self._async_request(
            "/hcb_config?action=getObjectConfigTree"
            "&package=happ_thermstat&internalAddress=thermostatStates"
        )
        if data is None:
            return

        try:
            matches = [
                int(state["id"][0])
                for state in data["states"][0]["state"]
                if int(state["tempValue"][0]) == setpoint
                and int(state["id"][0]) in PROGRAM_PRESET_STATES
            ]
        except (KeyError, IndexError, TypeError, ValueError) as err:
            _LOGGER.debug("%s: cannot parse preset temperatures: %s", self._device_name, err)
            return

        # Presets sharing a temperature leave the intended one ambiguous
        if len(matches) != 1:
            return

        _LOGGER.debug(
            "%s: setpoint %s matches preset state %s, activating it",
            self._device_name,
            setpoint,
            matches[0],
        )
        if await self._async_request(
            "/happ_thermstat?action=changeSchemeState"
            f"&state={SCHEME_STATE_TEMPORARY}&temperatureState={matches[0]}"
        ):
            await self._async_update_data()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode (none, comfort, home, sleep, away, eco)."""
        _LOGGER.debug("%s: set preset mode to '%s'", self._device_name, preset_mode)

        if preset_mode == PRESET_NONE:
            # Re-sending the current setpoint puts Toon in manual mode
            if self._current_setpoint is None:
                return
            path = (
                f"/happ_thermstat?action=setSetpoint&Setpoint={round(self._current_setpoint * 100)}"
            )
        else:
            scheme_state, temperature_state = PRESET_TO_SCHEME[preset_mode]
            path = (
                "/happ_thermstat?action=changeSchemeState"
                f"&state={scheme_state}&temperatureState={temperature_state}"
            )

        await self._async_send_command(path)
        await self._async_update_data()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug("%s: set hvac mode to '%s'", self._device_name, hvac_mode)

        if hvac_mode == HVACMode.HEAT:
            path = f"/happ_thermstat?action=changeSchemeState&state={SCHEME_STATE_PROGRAM_OFF}"
            if self._active_state == ACTIVE_STATE_HOLIDAY:
                # Leaving vacation mode needs an explicit preset to fall back to
                path += f"&temperatureState={ACTIVE_STATE_HOME}"
        else:
            path = f"/happ_thermstat?action=changeSchemeState&state={SCHEME_STATE_PROGRAM_ON}"

        await self._async_send_command(path)
        await self._async_update_data()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional Toon Thermostat status details."""
        next_preset = (
            ACTIVE_STATE_TO_PRESET.get(self._next_state) if self._next_state is not None else None
        )

        next_switch_local = (
            dt_util.as_local(self._next_switch_time) if self._next_switch_time else None
        )
        program_info: str | None = None
        if next_switch_local is not None and next_preset is not None:
            program_info = f"at {next_switch_local.strftime('%H:%M')} to {next_preset.capitalize()}"

        return {
            "burner_info": self._burner_info,
            "modulation_level": self._modulation_level,
            "current_internal_boiler_setpoint": self._current_internal_boiler_setpoint,
            "ot_comm_error": self._ot_comm_error,
            "program_state": self._program_state,
            "next_setpoint": self._next_setpoint,
            "next_state": next_preset,
            "next_switch_time": next_switch_local.isoformat() if next_switch_local else None,
            "program_info": program_info,
        }
