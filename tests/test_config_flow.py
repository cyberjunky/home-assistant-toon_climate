"""Tests for the Toon Climate config and options flows."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.toon_climate.const import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import ENTRY_OPTIONS, HOST, INFO_URL, PORT, thermostat_info


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent created entries from actually being set up."""
    with patch("custom_components.toon_climate.async_setup_entry", return_value=True) as mock:
        yield mock


async def test_user_flow(
    hass: HomeAssistant, mock_toon: AiohttpClientMocker, mock_setup_entry: AsyncMock
) -> None:
    """A reachable Toon creates an entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_NAME: "Living", CONF_MIN_TEMP: 10, CONF_SCAN_INTERVAL: 30},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT, CONF_NAME: "Living"}
    assert result["options"] == {
        CONF_MIN_TEMP: 10.0,
        CONF_MAX_TEMP: 30.0,
        CONF_SCAN_INTERVAL: 30,
    }
    assert result["result"].unique_id == HOST
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "mock_kwargs",
    [
        {"exc": aiohttp.ClientError()},
        {"exc": TimeoutError()},
        {"status": 404},
        {"text": "not json"},
    ],
)
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_kwargs: dict
) -> None:
    """Unreachable or invalid responses show cannot_connect, and the flow can recover."""
    aioclient_mock.get(INFO_URL, **mock_kwargs)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=thermostat_info())
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_toon: AiohttpClientMocker
) -> None:
    """A host that is already configured is aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """YAML config is imported; missing host and duplicates abort."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_NAME: "Toon", CONF_MAX_TEMP: 25.0},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT, CONF_NAME: "Toon"}
    assert result["options"][CONF_MAX_TEMP] == 25.0

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_import"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Changing only options does not contact the Toon."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_MIN_TEMP: 12, CONF_MAX_TEMP: 24, CONF_SCAN_INTERVAL: 60},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_MIN_TEMP: 12.0,
        CONF_MAX_TEMP: 24.0,
        CONF_SCAN_INTERVAL: 60,
    }
    assert aioclient_mock.call_count == 0


async def test_options_flow_change_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A new host is validated and stored together with a new unique_id."""
    mock_config_entry.add_to_hass(hass)
    new_host = "192.168.1.31"
    aioclient_mock.get(
        f"http://{new_host}:{PORT}/happ_thermstat?action=getThermostatInfo",
        json=thermostat_info(),
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOST: new_host, **ENTRY_OPTIONS}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data[CONF_HOST] == new_host
    assert mock_config_entry.unique_id == new_host


async def test_options_flow_host_errors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A host used by another entry, or an unreachable host, is rejected."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "10.0.0.2"}, unique_id="10.0.0.2").add_to_hass(
        hass
    )
    aioclient_mock.get(
        f"http://10.0.0.3:{PORT}/happ_thermstat?action=getThermostatInfo",
        exc=aiohttp.ClientError(),
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.2", **ENTRY_OPTIONS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.3", **ENTRY_OPTIONS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_config_entry.data[CONF_HOST] == HOST
