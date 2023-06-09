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
class GarageDoorBlockedSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "blocked"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    _garage_state: GarageDoorState

    def __init__(self, hass: HomeAssistant, state: GarageDoorState):
        self.hass = hass  # EntityPlatform sets this normally but to watch for events right away we need it earlier
        self._garage_state = state
        self._attr_unique_id = f"{self._garage_state.internal_id}_blocked"
        self._subscribe_state_changes()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._garage_state.internal_id)}, default_name="Garage Door",
                          suggested_area="Garage")

    @property
    def is_on(self) -> bool | None:
        return self._garage_state.error

    @property
    def icon(self) -> str | None:
        return 'mdi:sync-alert' if self._garage_state.error else 'mdi:sync'

    @property
    def should_poll(self) -> bool:
        return False

    def _subscribe_state_changes(self) -> None:
        door_uid = f"{self._garage_state.internal_id}_door"
        door_eid = er.async_get(self.hass).async_get_entity_id(Platform.COVER, DOMAIN, door_uid)

        if door_eid is None:  # this can happen when user disables door entity... which is nonsensical but possible
            _LOGGER.warning(f"{self.unique_id} will not be functional - no cover registered")

        async_track_state_change(self.hass, door_eid, self._on_cover_state_change)

    # @callback
    # async def on_opened_sensor_state_change(self, event: Event) -> None:
    @callback
    async def _on_cover_state_change(self, entity_id, old_state, new_state) -> None:
        self.async_write_ha_state()  # signal we may have an update - the is_on() is derived anyway
