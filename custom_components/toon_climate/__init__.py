"""Toon Climate integration for Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

# Schema for YAML configuration (legacy support for migration)
CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("climate"): vol.All(cv.ensure_list, [CLIMATE_SCHEMA]),
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_migrate_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old entities to new unique_id format.

    Old integration used entity_id like 'climate.toon' or 'climate.toon_thermostat'
    with unique_id format 'climate_{name}_{host}'.
    New format uses unique_id '{entry_id}_climate'.
    """
    entity_registry = er.async_get(hass)

    # Get values from the entry
    host = entry.data.get(CONF_HOST)
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    new_unique_id = f"{entry.entry_id}_climate"

    # Check if entity with new unique_id already exists
    if entity_registry.async_get_entity_id("climate", DOMAIN, new_unique_id):
        _LOGGER.debug("Entity with new unique_id already exists, skipping migration")
        return

    # Possible old unique_id formats
    old_unique_ids = [
        f"climate_{name}_{host}",
        f"climate_{DEFAULT_NAME}_{host}",
        f"climate_Toon_{host}",
    ]

    # First, try to find by old unique_id patterns
    for old_unique_id in old_unique_ids:
        # Check in toon_climate domain
        entity_id = entity_registry.async_get_entity_id("climate", DOMAIN, old_unique_id)

        # Also check if it was registered without platform (unlikely but check)
        if not entity_id:
            # Search all climate entities for matching unique_id
            for ent in entity_registry.entities.values():
                if ent.domain == "climate" and ent.unique_id == old_unique_id:
                    entity_id = ent.entity_id
                    break

        if entity_id:
            _LOGGER.info(
                "Migrating entity %s from old unique_id '%s' to '%s'",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
            entity_registry.async_update_entity(
                entity_id,
                new_unique_id=new_unique_id,
            )
            return

    # If not found by unique_id, try to find by common entity_id patterns
    # and check if it matches our host
    common_entity_ids = [
        "climate.toon",
        "climate.toon_thermostat",
        f"climate.{name.lower().replace(' ', '_')}",
    ]

    for common_entity_id in common_entity_ids:
        entity_entry = entity_registry.async_get(common_entity_id)
        if entity_entry and entity_entry.platform == DOMAIN:
            # Found an old entity from our integration
            _LOGGER.info(
                "Migrating entity %s to new unique_id '%s'",
                common_entity_id,
                new_unique_id,
            )
            entity_registry.async_update_entity(
                common_entity_id,
                new_unique_id=new_unique_id,
            )
            return

    _LOGGER.debug("No old entities found to migrate for host %s", host)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Toon Climate integration from YAML (legacy migration)."""
    hass.data.setdefault(DOMAIN, {})

    # Check for legacy climate platform configuration
    if "climate" in config:
        for platform_config in config["climate"]:
            if platform_config.get("platform") == DOMAIN:
                _LOGGER.warning(
                    "Configuration of Toon Climate via YAML platform is deprecated. "
                    "Your configuration has been imported. Please remove the YAML "
                    "configuration and restart Home Assistant."
                )
                # Import the configuration
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "import"},
                        data=platform_config,
                    )
                )

    # Check for new-style domain configuration
    if DOMAIN in config:
        domain_config = config[DOMAIN]
        if "climate" in domain_config:
            for climate_config in domain_config["climate"]:
                _LOGGER.warning(
                    "Configuration of Toon Climate via YAML is deprecated. "
                    "Your configuration has been imported. Please remove the YAML "
                    "configuration and restart Home Assistant."
                )
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "import"},
                        data=climate_config,
                    )
                )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toon Climate from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    # Migrate old entities to new unique_id format
    await async_migrate_entities(hass, entry)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Current version, no migration needed
        pass

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
