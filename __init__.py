from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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

    hass.data[DOMAIN][entry.entry_id] = GarageDoorState(entry.entry_id, controller)

    # Keys must match one of the types as per validation added in ~2023.8 and later moved:
    # https://github.com/home-assistant/core/pull/95641
    # https://github.com/home-assistant/core/commit/eee85666941439254567129d3ac57b74672a9ac4
    # https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/device_registry.py#L182C3-L182C3
    # ....or otherwise it will fail validation and not load the component, see e.g.
    #   https://github.com/home-assistant/core/pull/97843/files
    #   https://github.com/BenPru/luxtronik/pull/114/files
    # The check is pretty clever but non-obvious. You can have MISSING keys (e.g. sw_version) but you cannot have
    # ADDITIONAL keys. So, e.g. name+default_manufacturer will error out with a rather confusing error message.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hass.data[DOMAIN][entry.entry_id].internal_id)},
        manufacturer=ATTR_MANUFACTURER,
        model=ATTR_MODEL,
        name=entry.data[CONF_NAME],
        serial_number=entry.entry_id, # helpful for debugging and more ;)
        suggested_area=ATTR_DEFAULT_AREA,
        # via_device=None # can be set by going via ER => device, but this may cause order of registration issues? @todo
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
