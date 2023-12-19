"""Base class for all UpSmart Garage entities"""
from __future__ import annotations

from abc import abstractmethod

from .const import DOMAIN
from typing import TYPE_CHECKING
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_state_change

if TYPE_CHECKING:
    from .model import GarageDoorState

_LOGGER = logging.getLogger(__package__)


class UpSmartGarageEntity(Entity):
    _attr_has_entity_name = True
    _garage_state: GarageDoorState

    def __init__(self, hass: HomeAssistant, state: GarageDoorState, role: str):
        self.hass = hass  # EntityPlatform sets this normally but to watch for events right away we need it earlier
        self._garage_state = state
        self._attr_translation_key = role

        self._attr_unique_id = f"{self._garage_state.internal_id}_{role}"
        _LOGGER.debug(f"Registering entity {self._attr_unique_id}")
        self._subscribe_state_changes()

    @property
    def device_info(self) -> DeviceInfo:
        # This component uses explicit device registration over via-entity autoregistration - see __init__.py
        return DeviceInfo(identifiers={(DOMAIN, self._garage_state.internal_id)})

    @callback
    @abstractmethod
    def _subscribe_state_changes(self) -> None:
        pass


class UpSmartCoverDerivedEntity(UpSmartGarageEntity):
    @property
    def should_poll(self) -> bool:
        """State is updated to HA when cover triggers callback via _on_cover_state_change()"""
        return False

    def _subscribe_state_changes(self) -> None:
        door_uid = f"{self._garage_state.internal_id}_door"
        door_eid = er.async_get(self.hass).async_get_entity_id(Platform.COVER, DOMAIN, door_uid)

        # todo fix me:
        #  This also has some weird race condition when the device is first added to HASS. When cover is registered it
        #  isn't available right away in the entity registry. Once HASS is reloaded it is there... probably some state
        #  update call is missing when cover is registered, but I cannot locate it.
        if door_eid is None:  # this can happen when user disables door entity... which is nonsensical but possible
            _LOGGER.warning(f"{self.unique_id} will not be functional - no cover registered (expected {door_uid})")
            return

        _LOGGER.debug(f"{self.unique_id} is watching {door_uid} (entity_id={door_eid})")
        async_track_state_change(self.hass, door_eid, self._on_cover_state_change)

    @callback
    @abstractmethod
    async def _on_cover_state_change(self, entity_id, old_state, new_state) -> None:
        """Called any time the main cover entity state changes"""
        pass
