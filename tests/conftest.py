"""Fixtures for Toon Climate tests."""

import re
from typing import Any

import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.toon_climate.const import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

HOST = "192.168.1.30"
PORT = 80
INFO_URL = f"http://{HOST}:{PORT}/happ_thermstat?action=getThermostatInfo"
PRESETS_URL = (
    f"http://{HOST}:{PORT}/hcb_config?action=getObjectConfigTree"
    "&package=happ_thermstat&internalAddress=thermostatStates"
)
COMMAND_URL = re.compile(
    r"^http://192\.168\.1\.30(:80)?/happ_thermstat\?action=(setSetpoint|changeSchemeState)&"
)

ENTRY_DATA = {CONF_HOST: HOST, CONF_PORT: PORT, CONF_NAME: "Toon Thermostat"}
ENTRY_OPTIONS = {CONF_MIN_TEMP: 6.0, CONF_MAX_TEMP: 30.0, CONF_SCAN_INTERVAL: 10}


def thermostat_info(**overrides: str) -> dict[str, Any]:
    """Return a getThermostatInfo response: program on, home preset, burner heating."""
    return {
        "currentTemp": "2050",
        "currentSetpoint": "2000",
        "currentInternalBoilerSetpoint": "40",
        "programState": "1",
        "activeState": "1",
        "nextProgram": "1",
        "nextState": "2",
        "nextTime": "1700000000",
        "nextSetpoint": "1800",
        "burnerInfo": "1",
        "otCommError": "0",
        "currentModulationLevel": "30",
        **overrides,
    }


def preset_tree() -> dict[str, Any]:
    """Return a getObjectConfigTree response with the preset temperatures."""
    temps = {"0": "2100", "1": "1950", "2": "1500", "3": "1200"}
    return {
        "states": [{"state": [{"id": [k], "tempValue": [v]} for k, v in temps.items()]}],
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the custom integration in all tests."""
    return


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Toon Thermostat",
        data=dict(ENTRY_DATA),
        options=dict(ENTRY_OPTIONS),
        unique_id=HOST,
    )


@pytest.fixture
def mock_toon(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Serve thermostat info and accept commands on the mocked HTTP client."""
    aioclient_mock.get(INFO_URL, json=thermostat_info())
    aioclient_mock.get(PRESETS_URL, json=preset_tree())
    aioclient_mock.get(COMMAND_URL, json={"result": "ok"})
    return aioclient_mock
