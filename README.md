[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
![Project Maintenance][maintenance-shield]

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg?style=for-the-badge&logo=paypal)](https://www.paypal.me/cyberjunkynl/)
[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-GitHub-red.svg?style=for-the-badge&logo=github)](https://github.com/sponsors/cyberjunky)

# Toon Climate Component

This is a Custom Component for Home-Assistant (https://home-assistant.io) that provides a climate device for rooted Toon thermostats.

You can read and control thermostat mode and presets, read current temperature and control the setpoint.

Based on the standard behavior of the Toon the following two work modes are supported:

- Heat: Heat to a target temperature (schedule off)
- Auto: Follow the configured schedule as configured in your Toon (schedule on)

The following five presets are supported

- Away: This will change the setpoint to what you have configured in your Toon for the away state
- Home: This will change the setpoint to what you have configured in your Toon for the home state
- Comfort: This will change the setpoint to what you have configured in your Toon for the comfort state
- Sleep: This will change the setpoint to what you have configured in your Toon for the sleep state

(\*) The above four presets can be used independent of the selected work mode. - When the Toon is set to "heat" mode the preset will change the setpoint to the setpoint
configured for the respective preset. It will keep that setpoint until you change it manually
or switch to "auto" mode - When the Toon is set to "auto" mode the preset will change the setpoint to the setpoint configured
for the respective preset. However it will only change the setpoint temporatily until the schedule
changes to the next programmed preset.

- Eco: This will be used for the vacation mode the Toon offers. Regardless of the active work mode
  the preset will change the setpoint to the setpoint configured for the "vacation" setting. It
  will stay in this mode untill you change to one of the other four presets or chnage the work
  mode. So as long as the Toon is in eco (vacation) mode it will ensure the temperature does not
  drop below the set setpoint.

(\*) Please note that to use the "eco" (vacation) setpoint you will need to activate the vacation mode at
least once on your Toon. If not the setpoint will use the lowest temperature (6 degrees celcius)

NOTE: This component only works with rooted Toon devices.
Toon thermostats are available in The Netherlands and Belgium.

More information about rooting your Toon can be found here:
[Eneco Toon as Domotica controller](http://www.domoticaforum.eu/viewforum.php?f=87)

## Installation

### HACS - Recommended

- Have [HACS](https://hacs.xyz) installed, this will allow you to easily manage and track updates.
- Search for 'Toon Climate'.
- Click Install below the found integration.
- Configure using the configuration instructions below.
- Restart Home-Assistant.

### Manual

- Copy directory `custom_components/toon_climate` to your `<config dir>/custom_components` directory.
- Configure with config below.
- Restart Home-Assistant.

## Usage

To use this component in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry

climate:
  - platform: toon_climate
    name: Toon Thermostat
    host: IP_ADDRESS
    port: 80
    scan_interval: 10
    min_temp: 6.0
    max_temp: 30.0
```

Configuration variables:

- **name** (_Optional_): Name of the device. (default = 'Toon Thermostat')
- **host** (_Required_): The IP address on which the Toon can be reached.
- **port** (_Optional_): Port used by your Toon. (default = 80, other used port numbers can be 10080 or 7080)
- **scan_interval** (_Optional_): Number of seconds between polls. (default = 60)
- **min_temp** (_Optional_): Minimal temperature you can set (default = 6.0)
- **max_temp** (_Optional_): Maximal temperature you can set (default = 30.0)

## Screenshot

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon.png?raw=true "Screenshot Toon")

Toon with simple-thermostat in Lovelace

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-simple.png?raw=true "Toon simple-thermostat Screenshot")

Install Javascript from: https://github.com/nervetattoo/simple-thermostat

Using this card (replace 'climate.toon' with your device name if different):

```
   - type: 'custom:simple-thermostat'
     entity: climate.toon
     control:
       - preset
```

For the following examples please replace 'climate.toon' with your own climate device name if different.

If you want to automate changing the working mode of your Toon you can use the folowing scripts:

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

If you want to automate changing the standard presets of your Toon you can use the folowing scripts:

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

And in case you want to use the additional "vacation" feature you can use the following script:

```yaml
script:
  - toon_activate_preset_eco:
      alias: Toon activate preset Eco
      sequence:
        - service: climate.set_preset_mode
          data:
            preset_mode: eco
          entity_id: climate.toon
      mode: single
```

As a result the Toon Climate Component will put the Toon in "vacation" mode. In this mode none of the standard presets in
the Toon are activated. Instead it will use the setpoint that was set the last time the vacation mode on the Toon device
itself was actiated. It will ensure the room will not drop below that specific setpoint. This vacation mode will be cancelled
as soon as any of the presets on the Toon device are selected or by means of the Toon Climate Component being triggered
through either the climate card in Home Assistant or any related home assistant scripts or automation requests.

If you want a sensor that provides you with the current working mode of the Toon (manual, auto or vacation) add the following:

```yaml
sensor:
- platform: template
  sensors:
    toon_operation_mode:
      friendly_name: 'Programma'
        value_template: >-
        {% if is_state('climate.toon','off') %}
          Vakantie
        {% elif is_state('climate.toon','heat') %}
          Handmatig
        {% elif is_state('climate.toon','auto') %}
          Automatisch
        {% endif %}
```

If you want a sensor that allows you to show the current room temperature (e.g. in a badge) add the following:

```yaml
template:
  - sensor:
      - name: "Temperatuur Woonkamer"
        state: "{{ state_attr('climate.toon','current_temperature') }}"
        unit_of_measurement: °C
        device_class: temperature
        state_class: measurement
```

If you have a Toon2 and want to gather the environment sensor data you can create REST sensors like this:

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
        state: '{{ states.sensor.toon2_airsensors.attributes["humidity"] }}'
        device_class: humidity
        state_class: measurement
      - name: "Toon2 TVOC"
        state: '{{ states.sensor.toon2_airsensors.attributes["tvoc"] }}'
        device_class: volatile_organic_compounds
        state_class: measurement
      - name: "Toon2 eCO2"
        state: '{{ states.sensor.toon2_airsensors.attributes["eco2"] }}'
        device_class: carbon_dioxide
        state_class: measurement
```

You can create a sensor with more heating information like so:

```yaml
template:
  - sensor:
      - name: "Toon Driewegklep"
        state: >-
          {% if is_state_attr('climate.toon','burner_info', 0) %}
             Neutraal
          {% elif is_state_attr('climate.toon','burner_info', 1) %}
             CV
          {% elif is_state_attr('climate.toon','burner_info', 2) %}
             Warm Water
          {% endif %}
```

Trigger on burner state change (example from CV to Neutral):

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

You can also control the Toon device with Google's assistant.

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-setpoint.png?raw=true "Toon Assistant Setpoint")
![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-eco-preset.png?raw=true "Toon Assistant ECO Preset")

## Debugging

Add the relevant lines below to the `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.toon_climate: debug
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

[releases-shield]: https://img.shields.io/github/release/cyberjunky/home-assistant-toon_climate.svg?style=for-the-badge
[releases]: https://github.com/cyberjunky/home-assistant-toon_climate/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/cyberjunky/home-assistant-toon_climate.svg?style=for-the-badge
[commits]: https://github.com/cyberjunky/home-assistant-toon_climate/commits/main
[license-shield]: https://img.shields.io/github/license/cyberjunky/home-assistant-toon_climate.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-cyberjunky-blue.svg?style=for-the-badge
