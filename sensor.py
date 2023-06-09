from __future__ import annotations

import datetime
import time
from typing import TYPE_CHECKING
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers import entity_registry as er
from homeassistant.const import (Platform, UnitOfTime, EntityCategory)

from .const import DOMAIN
from .model import DoorState
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
    entities = []

    # Only add time-measuring sensors when we have a real sensor to actually measure the time
    if state.controller.opened_sensor:
        entities.append(GarageDoorOpenTime(hass, state))
    if state.controller.closed_sensor:
        entities.append(GarageDoorCloseTime(hass, state))

    async_add_entities(entities, True)


# The sensor exposes real time spent closing/opening the doors. This is more diagnostic, but can also be used for
# initial calibration if the uses so chooses.
class GarageTransitionTimeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_display_precision = 0

    _garage_state: GarageDoorState
    _accumulating: float | None = None
    _target_of_interest: DoorState

    def __init__(self, hass: HomeAssistant, state: GarageDoorState):
        self.hass = hass  # EntityPlatform sets this normally but to watch for events right away we need it earlier
        self._garage_state = state
        self._attr_unique_id = f"{self._garage_state.internal_id}_time_to_{self._target_of_interest.name.lower()}"
        self._subscribe_state_changes()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._garage_state.internal_id)}, default_name="Garage Door",
                          suggested_area="Garage")

    @property
    def should_poll(self) -> bool:
        return False

    def _subscribe_state_changes(self) -> None:
        door_uid = f"{self._garage_state.internal_id}_door"
        door_eid = er.async_get(self.hass).async_get_entity_id(Platform.COVER, DOMAIN, door_uid)

        if door_eid is None:  # this can happen when user disables door entity... which is nonsensical but possible
            _LOGGER.warning(f"{self.unique_id} will not be functional - no cover registered")

        async_track_state_change(self.hass, door_eid, self._on_cover_state_change)

    @callback
    async def _on_cover_state_change(self, entity_id, old_state, new_state) -> None:
        if self._garage_state.is_in_motion():
            # we only care about full transitions, not partial to avoid bogus data
            if self._garage_state.last_state != DoorState.PARTIALLY_OPEN and self._garage_state.last_state is not None \
               and self._garage_state.target_state == self._target_of_interest:
                self._accumulating = time.monotonic()
            return

        if self._accumulating is None:
            return

        if self._garage_state.error:  # we do not want to track errored-out states, only successful transitions
            self._accumulating = None
            return

        self._attr_native_value = time.monotonic() - self._accumulating
        self._accumulating = None
        self.async_write_ha_state()


class GarageDoorOpenTime(GarageTransitionTimeSensor):
    _attr_icon = "mdi:sort-clock-descending"
    _attr_translation_key = "time_to_opened"
    _target_of_interest: DoorState = DoorState.OPENED


class GarageDoorCloseTime(GarageTransitionTimeSensor):
    _attr_icon = "mdi:sort-clock-ascending"
    _attr_translation_key = "time_to_closed"
    _target_of_interest: DoorState = DoorState.CLOSED
