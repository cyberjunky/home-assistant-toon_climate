[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)  [![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/) [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)

This is a Custom Component for Home-Assistant (https://home-assistant.io) that provides a climate device for rooted Toon thermostats.

You can read and control thermostat mode and presets, read current temperature and control the setpoint.

NOTE: This component only works with rooted Toon devices.
Toon thermostats are available in The Netherlands and Belgium.

More information about rooting your Toon can be found here:
[Eneco Toon as Domotica controller](http://www.domoticaforum.eu/viewforum.php?f=87)

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
```

Configuration variables:

- **name** (*Optional*): Name of the device. (default = 'Toon Thermostat')
- **host** (*Required*): The IP address on which the Toon can be reached.
- **port** (*Optional*): Port used by your Toon. (default = 80, other used port numbers can be 10080 or 7080))
- **scan_interval** (*Optional*): Number of seconds between polls. (default = 60)
- **min_temp** (*Optional*): Minimal temperature you can set (default = 6.0)
- **max_temp** (*Optional*): Maximal temperature you can set (default = 25.0)

## Screenshot

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon.png?raw=true "Screenshot Toon")

Toon with simple-thermostat in Lovelace

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-simple.png?raw=true "Toon simple-thermostat Screenshot")

Using this card:
```
   - type: 'custom:simple-thermostat'
     entity: climate.toon
     control:
       - preset
```

You can create a sensor with more heating information like so (replace 'climate.toon' with your device name if different):

```yaml
sensor:
  - platform: template
    sensors:
      toon_driewegklep:
        friendly_name: 'Driewegklep'
        value_template: >-
          {% if is_state_attr('climate.toon','burner_info', 0) %}
             Neutraal
          {% elif is_state_attr('climate.toon','burner_info', 1) %}
             CV
          {% elif is_state_attr('climate.toon','burner_info', 2) %}
             Warm Water
          {% endif %}
```

You can also control it with Google's assistant

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-setpoint.png?raw=true "Toon Assistant Setpoint")
![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-eco-preset.png?raw=true "Toon Assistant ECO Preset")

## Donation
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)
