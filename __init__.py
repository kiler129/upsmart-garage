from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

import logging
from .const import *
from .config_flow import time_to_seconds
from .model import StateController, GarageDoorState

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.COVER,  # main garage door
    Platform.BINARY_SENSOR,  # report door stuck
    Platform.SENSOR,  # report last real open/close time
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Up-Smart Garage from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    open_time = time_to_seconds(entry.data[CONF_OPEN_TIME])
    close_time = time_to_seconds(entry.data[CONF_CLOSE_TIME])

    controller = StateController(entry.data[CONF_TOGGLE_RELAY],
                                 entry.data.get(CONF_CLOSED_SENSOR, None), close_time,
                                 entry.data.get(CONF_OPENED_SENSOR, None), open_time)
    if entry.data[CONF_INVERT_CLOSED_SENSOR]:
        controller.invert_closed_signal()
    if entry.data[CONF_INVERT_OPENED_SENSOR]:
        controller.invert_opened_signal()

    hass.data[DOMAIN][entry.entry_id] = \
        GarageDoorState(entry.entry_id, controller)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
