"""Sensor modules for Sensor Playground.

Each sensor class inherits from BaseSensor and implements:
    _init_hardware()  — attempt to initialise the physical sensor
    _read_hardware()  — return a dict of field→value from real hardware
    _simulate()       — return a dict of realistic fake data

The base class (sensors.base.BaseSensor) provides:
    read(demo)        — unified read with retry logic and error handling
    simulated         — property indicating whether hardware is available
    reliability       — percentage of successful reads
    close()           — release hardware resources
"""

from sensors.dht11 import DHT11Sensor
from sensors.pir import PIRSensor
from sensors.tilt import TiltSensor
from sensors.sound import SoundSensor
from sensors.knock import KnockSensor
from sensors.light import LightSensor
from sensors.reed import ReedSensor
from sensors.hall import HallSensor
from sensors.flame import FlameSensor
from sensors.touch import TouchSensor
from sensors.button import ButtonSensor
from sensors.ds18b20 import DS18B20Sensor
from sensors.rgb_led import RGBLEDSensor
from sensors.buzzer import BuzzerSensor
from sensors.sound_analog import SoundAnalogSensor
from sensors.light_analog import LightAnalogSensor
from sensors.soil_moisture import SoilMoistureSensor
from sensors.joystick import JoystickSensor
from sensors.tsl25911 import TSL25911Sensor
from sensors.ltr390 import LTR390Sensor
from sensors.bme280 import BME280Sensor
from sensors.sgp40 import SGP40Sensor
from sensors.icm20948 import ICM20948Sensor

SENSOR_CLASSES = {
    "dht11": DHT11Sensor,
    "pir": PIRSensor,
    "tilt": TiltSensor,
    "sound": SoundSensor,
    "knock": KnockSensor,
    "light": LightSensor,
    "reed": ReedSensor,
    "hall": HallSensor,
    "flame": FlameSensor,
    "touch": TouchSensor,
    "button": ButtonSensor,
    "ds18b20": DS18B20Sensor,
    "rgb_led": RGBLEDSensor,
    "buzzer": BuzzerSensor,
    "sound_analog": SoundAnalogSensor,
    "light_analog": LightAnalogSensor,
    "soil_moisture": SoilMoistureSensor,
    "joystick": JoystickSensor,
    "tsl25911": TSL25911Sensor,
    "ltr390": LTR390Sensor,
    "bme280": BME280Sensor,
    "sgp40": SGP40Sensor,
    "icm20948": ICM20948Sensor,
}
