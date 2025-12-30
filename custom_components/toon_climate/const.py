"""Constants for the Toon Climate integration."""

DOMAIN = "toon_climate"

# Configuration keys
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_SCAN_INTERVAL = "scan_interval"

# Default values
DEFAULT_NAME = "Toon Thermostat"
DEFAULT_PORT = 80
DEFAULT_MIN_TEMP = 6.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_SCAN_INTERVAL = 10

# Active states
ACTIVE_STATE_COMFORT = 0
ACTIVE_STATE_HOME = 1
ACTIVE_STATE_SLEEP = 2
ACTIVE_STATE_AWAY = 3
ACTIVE_STATE_HOLIDAY = 4

# Platforms
PLATFORMS = ["climate"]
