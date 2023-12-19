from __future__ import annotations

from typing import TYPE_CHECKING
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers import entity_registry as er
from homeassistant.const import Platform

from .const import DOMAIN
from .entity import UpSmartCoverDerivedEntity
if TYPE_CHECKING:
    from .model import GarageDoorState

_LOGGER = logging.getLogger(__package__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the actual door cover entity from config entry and central state"""
    state: GarageDoorState = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([GarageDoorBlockedSensor(hass, state)], True)


# The sensor exposes the error bit from the internal state. This is mainly intended to be used by e.g. HomeKit to report
# garage door being stuck while traveling.
class GarageDoorBlockedSensor(UpSmartCoverDerivedEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hass: HomeAssistant, state: GarageDoorState):
        super().__init__(hass, state, "blocked")

    @property
    def is_on(self) -> bool | None:
        return self._garage_state.error

    @property
    def icon(self) -> str | None:
        return 'mdi:sync-alert' if self._garage_state.error else 'mdi:sync'

    @callback
    async def _on_cover_state_change(self, entity_id, old_state, new_state) -> None:
        self.async_write_ha_state()  # signal we may have an update - the is_on() is derived anyway
