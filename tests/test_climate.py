"""Tests for the Toon Climate entity."""

from datetime import timedelta

import aiohttp
import pytest
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.toon_climate.const import CONF_MAX_TEMP, CONF_MIN_TEMP

from .conftest import (
    COMMAND_URL,
    ENTRY_DATA,
    ENTRY_OPTIONS,
    INFO_URL,
    PRESETS_URL,
    preset_tree,
    thermostat_info,
)

ENTITY_ID = "climate.toon_thermostat"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _serve(aioclient_mock: AiohttpClientMocker, command: dict | None = None, **info: str) -> None:
    """Replace the mocked responses (thermostat info, presets and commands)."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=thermostat_info(**info))
    aioclient_mock.get(PRESETS_URL, json=preset_tree())
    aioclient_mock.get(COMMAND_URL, json=command or {"result": "ok"})


def _commands(aioclient_mock: AiohttpClientMocker) -> list[dict[str, str]]:
    """Return the query of every command sent to the Toon."""
    return [
        dict(call[1].query)
        for call in aioclient_mock.mock_calls
        if call[1].query.get("action") in ("setSetpoint", "changeSchemeState")
    ]


async def test_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_toon: AiohttpClientMocker
) -> None:
    """The thermostat info is mapped onto the climate state and attributes."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.5
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOME
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_MIN_TEMP] == 6.0
    assert state.attributes[ATTR_MAX_TEMP] == 30.0
    assert state.attributes["modulation_level"] == 30
    assert state.attributes["next_setpoint"] == 18.0
    assert state.attributes["next_state"] == "sleep"
    expected_switch = dt_util.as_local(dt_util.utc_from_timestamp(1700000000))
    assert state.attributes["next_switch_time"] == expected_switch.isoformat()
    assert state.attributes["program_info"] == f"at {expected_switch:%H:%M} to Sleep"


async def test_state_heat_mode_idle(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Program off maps to heat mode; a manual setpoint to no preset; burner off to idle."""
    _serve(aioclient_mock, programState="0", activeState="-1", burnerInfo="0")
    await _setup(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_temperature_limits_clamped(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Configured limits outside what Toon accepts are clamped."""
    _serve(aioclient_mock)
    entry = MockConfigEntry(
        domain="toon_climate",
        data=dict(ENTRY_DATA),
        options={**ENTRY_OPTIONS, CONF_MIN_TEMP: 2.0, CONF_MAX_TEMP: 35.0},
    )
    await _setup(hass, entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MIN_TEMP] == 6.0
    assert state.attributes[ATTR_MAX_TEMP] == 30.0


@pytest.mark.parametrize(
    "mock_kwargs",
    [{"exc": aiohttp.ClientError()}, {"text": "not json"}, {"json": {"currentTemp": "2000"}}],
)
async def test_unavailable_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    mock_kwargs: dict,
) -> None:
    """Failed or incomplete responses mark the entity unavailable until a poll succeeds."""
    aioclient_mock.get(INFO_URL, **mock_kwargs)
    await _setup(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    _serve(aioclient_mock)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == HVACMode.AUTO


async def test_set_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Setting a temperature sends the setpoint in hundredths and refreshes."""
    _serve(aioclient_mock, programState="0")
    await _setup(hass, mock_config_entry)
    _serve(aioclient_mock, programState="0", currentSetpoint="2150")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )

    assert _commands(aioclient_mock) == [{"action": "setSetpoint", "Setpoint": "2150"}]
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 21.5


async def test_set_temperature_activates_matching_preset(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """In program mode, a setpoint equal to a preset temperature activates that preset."""
    _serve(aioclient_mock)
    await _setup(hass, mock_config_entry)
    _serve(aioclient_mock, activeState="-1", currentSetpoint="2100")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )

    assert _commands(aioclient_mock) == [
        {"action": "setSetpoint", "Setpoint": "2100"},
        {"action": "changeSchemeState", "state": "2", "temperatureState": "0"},
    ]


@pytest.mark.parametrize(
    ("preset", "command"),
    [
        (PRESET_AWAY, {"action": "changeSchemeState", "state": "2", "temperatureState": "3"}),
        (PRESET_ECO, {"action": "changeSchemeState", "state": "8", "temperatureState": "4"}),
        (PRESET_NONE, {"action": "setSetpoint", "Setpoint": "2000"}),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toon: AiohttpClientMocker,
    preset: str,
    command: dict[str, str],
) -> None:
    """Presets map onto changeSchemeState; 'none' re-sends the current setpoint."""
    await _setup(hass, mock_config_entry)
    _serve(mock_toon)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    assert _commands(mock_toon) == [command]


@pytest.mark.parametrize(
    ("hvac_mode", "active_state", "command"),
    [
        (HVACMode.AUTO, "1", {"action": "changeSchemeState", "state": "1"}),
        (HVACMode.HEAT, "1", {"action": "changeSchemeState", "state": "0"}),
        (
            HVACMode.HEAT,
            "4",
            {"action": "changeSchemeState", "state": "0", "temperatureState": "1"},
        ),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    hvac_mode: HVACMode,
    active_state: str,
    command: dict[str, str],
) -> None:
    """HVAC modes switch the program; leaving vacation mode falls back to home."""
    _serve(aioclient_mock, activeState=active_state)
    await _setup(hass, mock_config_entry)
    _serve(aioclient_mock, activeState=active_state)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    assert _commands(aioclient_mock) == [command]


async def test_command_failure_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A command the Toon rejects raises a HomeAssistantError."""
    _serve(aioclient_mock)
    await _setup(hass, mock_config_entry)
    _serve(aioclient_mock, command={"success": False})

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )
