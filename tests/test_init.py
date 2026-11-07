"""Tests for setting up and unloading the Toon Climate integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.toon_climate.const import CONF_SCAN_INTERVAL, DOMAIN

from .conftest import ENTRY_OPTIONS, HOST


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_toon: AiohttpClientMocker
) -> None:
    """The entry sets up the climate entity and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.toon_thermostat") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_options_update_reloads(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_toon: AiohttpClientMocker
) -> None:
    """Changing the options reloads the entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    calls_before = mock_toon.call_count

    hass.config_entries.async_update_entry(
        mock_config_entry, options={**ENTRY_OPTIONS, CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # The reloaded entity fetches the thermostat info again
    assert mock_toon.call_count == calls_before + 1


async def test_migrate_legacy_unique_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_toon: AiohttpClientMocker
) -> None:
    """The old climate_{name}_{host} unique_id is rewritten, keeping the entity_id."""
    mock_config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    old = ent_reg.async_get_or_create(
        "climate", DOMAIN, f"climate_Toon Thermostat_{HOST}", suggested_object_id="toon"
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ent_reg.async_get(old.entity_id).unique_id == f"{mock_config_entry.entry_id}_climate"
    assert hass.states.get("climate.toon") is not None


async def test_migrate_by_entity_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_toon: AiohttpClientMocker
) -> None:
    """An old entity is also found through its well-known entity_id."""
    mock_config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "climate", DOMAIN, "something-else", suggested_object_id="toon_thermostat"
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = ent_reg.async_get("climate.toon_thermostat")
    assert entry.unique_id == f"{mock_config_entry.entry_id}_climate"


async def test_yaml_domain_import(hass: HomeAssistant, mock_toon: AiohttpClientMocker) -> None:
    """Domain-style YAML is imported and a deprecation issue is raised."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"climate": [{CONF_HOST: HOST}]}})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == HOST
    assert ir.async_get(hass).async_get_issue(DOMAIN, "deprecated_yaml") is not None


async def test_yaml_platform_import(hass: HomeAssistant, mock_toon: AiohttpClientMocker) -> None:
    """Legacy 'climate: - platform: toon_climate' YAML is imported as well."""
    assert await async_setup_component(
        hass, "climate", {"climate": [{"platform": DOMAIN, CONF_HOST: HOST}]}
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == HOST
