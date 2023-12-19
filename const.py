"""Constants for the Scrypted integration."""
from typing import Final

DOMAIN: Final = "upsmart_garage"
ATTR_MANUFACTURER: Final = "https://github.com/kiler129"
ATTR_MODEL: Final = "Up-Smart Garage"
ATTR_DEFAULT_AREA: Final = "Garage"
ATTR_NAME: Final = "Garage Door"

CONF_NAME: Final = "name"
CONF_TOGGLE_RELAY: Final = "state_toggle_relay"
CONF_CLOSED_SENSOR: Final = "closed_sensor"
CONF_INVERT_CLOSED_SENSOR: Final = "invert_closed_sensor"
CONF_OPENED_SENSOR: Final = "opened_sensor"
CONF_INVERT_OPENED_SENSOR: Final = "invert_opened_sensor"
CONF_OPEN_TIME: Final = "open_time"
CONF_CLOSE_TIME: Final = "close_time"
