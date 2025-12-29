[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
![Project Maintenance][maintenance-shield]

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg?style=for-the-badge&logo=paypal)](https://www.paypal.me/cyberjunkynl/)
[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-GitHub-red.svg?style=for-the-badge&logo=github)](https://github.com/sponsors/cyberjunky)

# Toon Climate Custom Integration

A Home Assistant custom integration for controlling rooted Toon thermostats. Monitor and control HVAC mode, temperature setpoint, and preset modes.

## Supported Features

**HVAC Modes:**
- **Heat**: Manual mode - heat to target temperature (schedule off)
- **Auto**: Automatic mode - follow Toon's schedule (schedule on)

**Presets:**
- **Away**: Away mode setpoint
- **Home**: Home mode setpoint
- **Comfort**: Comfort mode setpoint
- **Sleep**: Sleep mode setpoint
- **Eco**: Vacation mode (requires manual activation on device first; uses 6°C minimum by default)

## Requirements

- Rooted Toon thermostat
- Available in The Netherlands and Belgium
- More info: [Eneco Toon Domotica Forum](http://www.domoticaforum.eu/viewforum.php?f=87)

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cyberjunky&repository=home-assistant-toon_climate&category=integration)

Alternatively:
1. Install [HACS](https://hacs.xyz) if not already installed
2. Search for "Toon Climate" in HACS
3. Click **Download**
4. Restart Home Assistant
5. Add via Settings → Devices & Services

### Manual Installation

1. Copy `custom_components/toon_climate` to your `<config>/custom_components/` directory
2. Restart Home Assistant
3. Add via Settings → Devices & Services

## Configuration

### Adding the Integration

1. Navigate to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Toon Climate"**
4. Enter your configuration:
   - **Host**: Your Toon's IP address
   - **Port**: Default is `80`
   - **Name**: Friendly name (default: "Toon Thermostat")
   - **Minimum Temperature**: The minimum temperature which can be set
   - **Maximum Temperature**: The maximum temperature which can be set
   - **Update Interval**: Seconds between updates (default: `30`)

### Migrating from YAML

> **Note:** YAML configuration is deprecated as of v2.0.0

If you previously configured this integration in `configuration.yaml`, your settings will be **automatically imported** on your first restart after updating.

**Your old YAML config** (will be migrated):

```yaml
climate:
  - platform: toon_climate
    name: Toon
    scan_interval: 90
    host: !secret toon_host
```

**After migration:**

1. Remove the YAML configuration from `configuration.yaml`
2. Manage all settings via **Settings** → **Devices & Services** → **Toon Climate** → **Configure**
3. Disable unwanted sensors through entity settings

### Modifying Settings

Change integration settings without restarting Home Assistant:

1. Go to **Settings** → **Devices & Services**
2. Find **Toon Climate**
3. Click **Configure** icon
4. Modify setting(s)
5. Click **Submit**

Changes apply immediately. To enable/disable individual sensors, click on the sensor entity and toggle "Enable entity".

## Screenshots

<p align="center">
  <a href="https://github.com/cyberjunky/home-assistant-toon_climate/raw/master/screenshots/setup.png" target="_blank" title="Screenshot Toon Setup">
    <img src="https://github.com/cyberjunky/home-assistant-toon_climate/raw/master/screenshots/setup.png" alt="Setup" width="220" style="margin-right:8px;" />
  </a>
  <a href="https://github.com/cyberjunky/home-assistant-toon_climate/raw/master/screenshots/comfort.png" target="_blank" title="Screenshot Toon Thermostat">
    <img src="https://github.com/cyberjunky/home-assistant-toon_climate/raw/master/screenshots/comfort.png" alt="Comfort" width="220" style="margin-right:8px;" />
  </a>
  <a href="https://github.com/cyberjunky/home-assistant-toon_climate/raw/master/screenshots/history.png" target="_blank" title="Screenshot Toon History">
    <img src="https://github.com/cyberjunky/home-assistant-toon_climate/raw/master/screenshots/history.png" alt="History" width="220" />
  </a>
</p>

## Automation Examples

Replace `climate.toon` with your entity ID.

**Switch HVAC modes:**

```yaml
script:
  - toon_enable_manual_mode:
      alias: Toon enable Manual mode
      sequence:
        - service: climate.set_hvac_mode
          data:
            hvac_mode: "heat"
          entity_id: climate.toon
      mode: single
  - toon_enable_schedule_mode:
      alias: Toon enable Schedule mode
      sequence:
        - service: climate.set_hvac_mode
          data:
            hvac_mode: "auto"
          entity_id: climate.toon
      mode: single
```

**Change presets:**

```yaml
script:
  - toon_activate_preset_comfort:
      alias: Toon activate preset Comfort
      sequence:
        - service: climate.set_preset_mode
          data:
            preset_mode: "comfort"
          entity_id: climate.toon
      mode: single
  - toon_activate_preset_away:
      alias: Toon activate preset Away
      sequence:
        - service: climate.set_preset_mode
          data:
            preset_mode: "away"
          entity_id: climate.toon
      mode: single
  - toon_activate_preset_home:
      alias: Toon activate preset Home
      sequence:
        - service: climate.set_preset_mode
          data:
            preset_mode: "home"
          entity_id: climate.toon
      mode: single
  - toon_activate_preset_sleep:
      alias: Toon activate preset Sleep
      sequence:
        - service: climate.set_preset_mode
          data:
            preset_mode: "sleep"
          entity_id: climate.toon
      mode: single
```

**Activate vacation mode:**

```yaml
script:
  - toon_activate_preset_eco:
      alias: Toon activate preset Eco (Vacation)
      sequence:
        - service: climate.set_preset_mode
          data:
            preset_mode: eco
          entity_id: climate.toon
      mode: single
```

When activated, the Eco preset enables vacation mode and maintains the last set vacation temperature as the minimum. Exit by selecting any other preset.

## Template Sensors

**Current operation mode:**

```yaml
template:
  - sensor:
      - name: "Toon Operation Mode"
        unique_id: toon_operation_mode
        state: >-
          {% if is_state('climate.toon','off') %}
            Vakantie
          {% elif is_state('climate.toon','heat') %}
            Handmatig
          {% elif is_state('climate.toon','auto') %}
            Automatisch
          {% endif %}
```

**Current room temperature:**

```yaml
template:
  - sensor:
      - name: "Temperatuur Woonkamer"
        unique_id: toon_current_temperature
        state: "{{ state_attr('climate.toon', 'current_temperature') }}"
        unit_of_measurement: °C
        device_class: temperature
        state_class: measurement
```

**Toon2 environment sensors:**

```yaml
sensor:
  - platform: rest
    name: Toon2 AirSensors
    json_attributes:
      - humidity
      - tvoc
      - eco2
    value_template: '{{ value_json["temperature"] }}'
    device_class: temperature
    unit_of_measurement: "°C"
    resource: http://192.168.2.106/tsc/sensors

template:
  - sensor:
      - name: "Toon2 Humidity"
        unique_id: toon2_humidity
        state: '{{ state_attr("sensor.toon2_airsensors", "humidity") }}'
        device_class: humidity
        state_class: measurement
        unit_of_measurement: "%"
      - name: "Toon2 TVOC"
        unique_id: toon2_tvoc
        state: '{{ state_attr("sensor.toon2_airsensors", "tvoc") }}'
        device_class: volatile_organic_compounds
        state_class: measurement
        unit_of_measurement: "ppb"
      - name: "Toon2 eCO2"
        unique_id: toon2_eco2
        state: '{{ state_attr("sensor.toon2_airsensors", "eco2") }}'
        device_class: carbon_dioxide
        state_class: measurement
        unit_of_measurement: "ppm"
```

You can create a sensor with more heating information like so:

```yaml
template:
  - sensor:
      - name: "Toon Driewegklep"
        unique_id: toon_burner_valve
        state: >-
          {% if is_state_attr('climate.toon', 'burner_info', 0) %}
            Neutraal
          {% elif is_state_attr('climate.toon', 'burner_info', 1) %}
            CV
          {% elif is_state_attr('climate.toon', 'burner_info', 2) %}
            Warm Water
          {% endif %}
```

**Detect burner state changes:**

```yaml
automation:
  - alias: "Detect Burnerstate change"
    trigger:
      platform: state
      entity_id: climate.toon_thermostat
    condition:
      condition: template
      value_template: >
        {{ trigger.from_state and
            trigger.to_state.attributes.burner_info == 0 and
            trigger.from_state.attributes.burner_info == 1}}
    action:
      service: persistent_notification.create
      data:
        message: Burner state changed!
        title: "Thermostat Info"
```

## Debugging

Add the relevant lines below to the `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.toon_climate: debug
```

## Development

Quick-start (from project root):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements_lint.txt
./scripts/lint    # runs pre-commit + vulture
# or: ruff check .
# to auto-fix: ruff check . --fix
```


## 💖 Support This Project

If you find this library useful for your projects, please consider supporting its continued development and maintenance:

### 🌟 Ways to Support

- **⭐ Star this repository** - Help others discover the project
- **💰 Financial Support** - Contribute to development and hosting costs
- **🐛 Report Issues** - Help improve stability and compatibility
- **📖 Spread the Word** - Share with other developers

### 💳 Financial Support Options

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg?style=for-the-badge&logo=paypal)](https://www.paypal.me/cyberjunkynl/)
[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-GitHub-red.svg?style=for-the-badge&logo=github)](https://github.com/sponsors/cyberjunky)

**Why Support?**

- Keeps the project actively maintained
- Enables faster bug fixes and new features
- Supports infrastructure costs (testing, AI, CI/CD)
- Shows appreciation for hundreds of hours of development

Every contribution, no matter the size, makes a difference and is greatly appreciated! 🙏

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

[releases-shield]: https://img.shields.io/github/release/cyberjunky/home-assistant-toon_climate.svg?style=for-the-badge
[releases]: https://github.com/cyberjunky/home-assistant-toon_climate/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/cyberjunky/home-assistant-toon_climate.svg?style=for-the-badge
[commits]: https://github.com/cyberjunky/home-assistant-toon_climate/commits/main
[license-shield]: https://img.shields.io/github/license/cyberjunky/home-assistant-toon_climate.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-cyberjunky-blue.svg?style=for-the-badge
