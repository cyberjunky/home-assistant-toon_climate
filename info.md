[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)  [![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/) [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)

# Toon Climate Component
This is a Custom Component for Home-Assistant (https://home-assistant.io) that provides a climate device for rooted Toon thermostats.

You can read and control thermostat mode and presets, read current temperature and control the setpoint.

Based on the standard behavior of the Toon the following two work modes are supported:
- Heat:     Heat to a target temperature (schedule off)
- Auto:     Follow the configured schedule as configured in your Toon (schedule on)

The following five presets are supported
- Away:     This will change the setpoint to what you have configured in your Toon for the away state
- Home:     This will change the setpoint to what you have configured in your Toon for the home state
- Comfort:  This will change the setpoint to what you have configured in your Toon for the comfort state
- Sleep:    This will change the setpoint to what you have configured in your Toon for the sleep state

(*) The above four presets can be used independent of the selected work mode.
    -   When the Toon is set to "heat" mode the preset will change the setpoint to the setpoint
        configured for the respective preset. It will keep that setpoint until you change it manually 
        or switch to "auto" mode
    -   When the Toon is set to "auto" mode the preset will change the setpoint to the setpoint configured
        for the respective preset. However it will only change the setpoint temporatily until the schedule 
        changes to the next programmed preset. 

- Eco:      This will be used for the vacation mode the Toon offers. Regardless of the active work mode
            the preset will change the setpoint to the setpoint configured for the "vacation" setting. It
            will stay in this mode untill you change to one of the other four presets or chnage the work 
            mode. So as long as the Toon is in eco (vacation) mode it will ensure the temperature does not
            drop below the set setpoint.
            
(*) Please note that to use the "eco" (vacation) setpoint you will need to activate the vacation mode at 
    least once on your Toon. If not the setpoint will use the lowest temperature (6 degrees celcius)

NOTE: This component only works with rooted Toon devices.
Toon thermostats are available in The Netherlands and Belgium.

More information about rooting your Toon can be found here:
[Eneco Toon as Domotica controller](http://www.domoticaforum.eu/viewforum.php?f=87)

## Installation

- Install this integration using HACS.
- Configure using configuration instructions below.
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

- **name** (*Optional*): Name of the device. (default = 'Toon Thermostat')
- **host** (*Required*): The IP address on which the Toon can be reached.
- **port** (*Optional*): Port used by your Toon. (default = 80, other used port numbers can be 10080 or 7080)
- **scan_interval** (*Optional*): Number of seconds between polls. (default = 60)
- **min_temp** (*Optional*): Minimal temperature you can set (default = 6.0)
- **max_temp** (*Optional*): Maximal temperature you can set (default = 30.0)

## Screenshot

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon.png?raw=true "Screenshot Toon")

Toon with simple-thermostat in Lovelace

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-simple.png?raw=true "Toon simple-thermostat Screenshot")

Install Javascript from: https://github.com/nervetattoo/simple-thermostat

Using this card:
```
   - type: 'custom:simple-thermostat'
     entity: climate.toon_thermostat
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

If you want the room temperature in a badge do this:
```yaml
sensor:
  - platform: template
    sensors:
      temperatuur_woonkamer:
        friendly_name: "Temperatuur Woonkamer"
        value_template: "{{ state_attr('climate.toon','current_temperature') }}"
        unit_of_measurement: °C
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
    unit_of_measurement: "°C"
    resource: http://192.168.2.106/tsc/sensors

  - platform: template
    sensors:
      toon2_humidity:
        friendly_name: "Humidity"
        value_template: '{{ states.sensor.toon2_airsensors.attributes["humidity"] }}'
        unit_of_measurement: "%"
      toon2_tvoc:
        friendly_name: "TVOC"
        value_template: '{{ states.sensor.toon2_airsensors.attributes["tvoc"] }}'
        unit_of_measurement: "ppm"
      toon2_eco2:
        friendly_name: "ECO2"
        value_template: '{{ states.sensor.toon2_airsensors.attributes["eco2"] }}'
        unit_of_measurement: "?"
```
          
You can also control it with Google's assistant

![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-setpoint.png?raw=true "Toon Assistant Setpoint")
![alt text](https://github.com/cyberjunky/home-assistant-toon_climate/blob/master/screenshots/toon-eco-preset.png?raw=true "Toon Assistant ECO Preset")

## Donation
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)
