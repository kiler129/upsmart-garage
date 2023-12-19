from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final, Any

import logging
import datetime

import asyncio
from homeassistant.core import HomeAssistant, Event, callback, CALLBACK_TYPE
from homeassistant.components.cover import CoverEntity, CoverDeviceClass, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .entity import UpSmartGarageEntity
from .model import DoorState
if TYPE_CHECKING:
    from .model import GarageDoorState

_LOGGER = logging.getLogger(__package__)
# SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the actual door cover entity from config entry and central state"""
    state: GarageDoorState = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([UpSmartGarageCover(hass, state)], True)


# The cover is the main state machine for the integration. Other entities derive its state from what the cover persists
# in the GarageDoorState.
class UpSmartGarageCover(UpSmartGarageEntity, CoverEntity):
    _transition_grace_multiplier: Final[float] = 1.1
    _attr_icon = "mdi:garage"
    _attr_device_class = CoverDeviceClass.GARAGE

    _garage_state: GarageDoorState
    _transition_timer: CALLBACK_TYPE | None = None  # in transition; watching for the typical delta+10% (i.e. failsafe)
    _sensor_closed: bool | None = None  # if we have sensor for fully closed it will signify its state
    _sensor_opened: bool | None = None  # if we have sensor for fully open it will signify its state
    _toggle_state: bool | None = None  # toggle button state used to control the open/close/stop action of the door

    def __init__(self, hass: HomeAssistant, state: GarageDoorState):
        super().__init__(hass, state, "door")
        self._sync_state()

    @property
    def supported_features(self) -> CoverEntityFeature:
        return CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP

    @property
    def current_cover_position(self) -> int | None:
        """Attempts to derive door position based on time to open/close them"""
        if not self._garage_state.is_in_motion():
            match self._garage_state.last_state:
                case DoorState.OPENED:
                    return 100
                case DoorState.PARTIALLY_OPEN:
                    return 50
                case DoorState.CLOSED:
                    return 0
                case None:
                    return None

        if self._garage_state.last_state is None:
            _LOGGER.debug(f"{self.unique_id} guessed current position as 50% as last state is unknown")
            return 50

        real_delta = time.monotonic() - self._garage_state.transition_triggered
        expected_delta = self._garage_state.delta_for_current_state
        if real_delta > expected_delta:  # most likely stuck somewhere
            _LOGGER.debug(f"{self.unique_id} current position unknown - time delta {real_delta}s > {expected_delta}s")
            return None

        transition_pos = int(round(real_delta/expected_delta))
        return transition_pos if self._garage_state.target_state == DoorState.OPENED else 100-transition_pos

    @property
    def is_closed(self) -> bool | None:
        """Determines whether the door is FULLY closed"""
        # even if last_state is unknown, when door is in motion we know it cannot be (fully) closed, regardless if we
        # can determine whether it's closING or openING
        _LOGGER.debug(f"isClosed? lstate={self._garage_state.last_state} result={self._garage_state.last_state == DoorState.CLOSED and not self._garage_state.is_in_motion()}")
        return self._garage_state.last_state == DoorState.CLOSED and not self._garage_state.is_in_motion()

    @property
    def is_open(self) -> bool | None:
        """Determines whether the door is FULLY opened"""
        # even if last_state is unknown, when door is in motion we know it cannot be (fully) open, regardless if we
        # can determine whether it's closING or openING
        debug_target = (self._garage_state.last_state == DoorState.OPENED and not self._garage_state.is_in_motion()) or self._garage_state.last_state == DoorState.PARTIALLY_OPEN
        _LOGGER.debug(f"isOpen? lstate={self._garage_state.last_state} result={debug_target}")
        return (self._garage_state.last_state == DoorState.OPENED and not self._garage_state.is_in_motion()) or \
            self._garage_state.last_state == DoorState.PARTIALLY_OPEN

    @property
    def is_opening(self) -> bool | None:
        """Determines whether the door is currently moving in the close-to-open direction"""
        if self._garage_state.last_state is None:  # if last state is unknown we don't know if it's opening or closing
            _LOGGER.debug("isOpening? lstate=None => result=None")
            return None

        _LOGGER.debug(f"isOpening? lstate={self._garage_state.last_state} "
                      f"target={self._garage_state.target_state} => " 
                      f"result={self._garage_state.target_state == DoorState.OPENED}")
        return self._garage_state.target_state == DoorState.OPENED

    @property
    def is_closing(self) -> bool | None:
        """Determines whether the door is currently moving in the (partially-)open-to-close direction"""
        if self._garage_state.last_state is None:  # if last state is unknown we don't know if it's opening or closing
            _LOGGER.debug("isClosing? => None")
            return None
        _LOGGER.debug(f"isClosing? => target={self._garage_state.target_state} result={self._garage_state.target_state == DoorState.CLOSED}")
        return self._garage_state.target_state == DoorState.CLOSED

    @property
    def icon(self) -> str:
        if self._garage_state.is_in_motion() or self._garage_state.last_state != DoorState.CLOSED:
            return 'mdi:garage-open'

        return 'mdi:garage-alert' if self._garage_state.error else 'mdi:garage'

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        # While realistically it could be possible to kind-of implement this based on the open/close time, it will be
        # probably grossly inaccurate and prone to failures. This is because typical door motion isn't linear and the
        # time is only semi-predictable when starting from the bottom or top (i.e. time-to-close when open at 50% isn't
        # equal to time-to-close/2)
        raise NotImplementedError()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Performs fully closed to open transition"""
        _LOGGER.debug(f"Open requested for {self.unique_id}")
        if self.is_opening:
            _LOGGER.warning(f"Attempted to open {self.unique_id} when it is already opening")
            return

        if self.is_closing:
            _LOGGER.debug(f"{self.unique_id} is closing - stopping first")
            await self.async_stop_cover()

        await self._do_transition_state(DoorState.OPENED)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Performs open/partially-open to close transition"""
        _LOGGER.debug(f"Close requested for {self.unique_id}")
        if self.is_closing:
            _LOGGER.warning(f"Attempted to close {self.unique_id} when it is already closing")
            return

        if self.is_opening:
            _LOGGER.debug(f"{self.unique_id} is opening - stopping first")
            await self.async_stop_cover()

        await self._do_transition_state(DoorState.CLOSED)

    async def _do_transition_state(self, state: DoorState) -> None:
        """Generic open-to-close / close-to-open transition function"""
        # Attempt transition first, to make sure the intended action conforms to the state machine
        try:
            self._garage_state.transition(state)
        except ValueError as e:
            _LOGGER.error(e)

        # Realistically, we hope that open/close sensor will trip before this timer. However, this lets us determine if
        # the door maybe stopped in the middle before reaching the sensor. In addition, this timer is required to
        # emulate door hitting the position where there may not be a sensor (e.g. user only has close but not open
        # sensor)
        max_expected_time = self._garage_state.delta_for_current_state * self._transition_grace_multiplier
        self._transition_timer = async_call_later(self.hass, max_expected_time, self.on_transition_timer_finish)
        _LOGGER.debug(f"{self.unique_id} will be transitioning " 
                      f"{self._garage_state.last_state} => {state.name} in max {max_expected_time}s")

        await self._pulse_toggle()
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        if not self._garage_state.is_in_motion():
            _LOGGER.warning(f"{self.unique_id} not in motion - not stopping")
            return

        # Attempt transition first, to make sure the intended action conforms to the state machine
        _LOGGER.debug(f"{self.unique_id} stopping on request")
        try:
            self._garage_state.abort_transition()
        except ValueError as e:
            _LOGGER.error(e)

        # take care of the timer as manually stopping the cover is physically equivalent of it getting stuck but on
        # purpose. However, it is not an error condition per-se.
        if self._transition_timer is not None:
            self._transition_timer()

        await self._pulse_toggle()
        self.async_write_ha_state()

    async def _pulse_toggle(self) -> None:
        """Causes a physical toggle on-wait-off to be sent to the garage door controller without any logic"""
        _LOGGER.debug(f"Toggle pulse requested for {self.unique_id}")
        if self._toggle_state:
            _LOGGER.warning(f"Toggle pulse denied - another one in progress")
            return

        if self._toggle_state is None:  # this can happen esp. when the integration started before relay integration
            _LOGGER.warning(f"Toggle in unknown state - attempting pulse anyway")

        await self.hass.services.async_call('homeassistant', 'turn_on',
                                            {'entity_id': self._garage_state.controller.toggle_controller})
        self._toggle_state = True
        # cannot use async_call_later() here, as we need an async job to await, making rest of the code simpler
        await asyncio.sleep(self._garage_state.controller.pulse_time)
        _LOGGER.debug(f"Toggle pulse finished for {self.unique_id}")
        await self.hass.services.async_call('homeassistant', 'turn_off',
                                            {'entity_id': self._garage_state.controller.toggle_controller})
        self._toggle_state = False
        self._garage_state.error = False  # clear error if any; we moved the door (presumably)

    def _subscribe_state_changes(self) -> None:
        """Observes changes in the physical world to develop a virtual state"""
        if self._garage_state.controller.closed_sensor is not None:
            _LOGGER.debug(f"{self.unique_id} has closed sensor - subscribing")
            async_track_state_change_event(self.hass, self._garage_state.controller.closed_sensor,
                                           self.on_closed_sensor_state_change)
            self.read_closed_sensor()

        if self._garage_state.controller.opened_sensor is not None:
            _LOGGER.debug(f"{self.unique_id} has opened sensor - subscribing")
            async_track_state_change_event(self.hass, self._garage_state.controller.opened_sensor,
                                           self.on_opened_sensor_state_change)
            self.read_opened_sensor()

        async_track_state_change_event(self.hass, self._garage_state.controller.toggle_controller,
                                       self.on_toggle_state_change)
        self._toggle_state = self._do_read_binary_state(self._garage_state.controller.toggle_controller)

    @callback
    async def on_closed_sensor_state_change(self, event: Event) -> None:
        """Triggers when door-fully-closed sensor changes its state"""
        self.read_closed_sensor(event.data.get('new_state').state)
        self._ensure_no_sensor_state_conflict()

        if not self._garage_state.is_in_motion():  # door was opened or closed externally
            # we don't need to check _sensor_opened here (it will be None or False) as _ensure_no_sensor_state_conflict
            # guarantees it is not True when _sensor_closed is True
            state = DoorState.CLOSED if self._sensor_closed else DoorState.OPENED
            self._garage_state.force_state(state)
            _LOGGER.debug(f"{self.unique_id} closed sensor tripped when not in motion - computed {state}")
            self.async_write_ha_state()
            return

        if self._sensor_closed:  # sensor indicates that the door has closed
            if self._garage_state.target_state == DoorState.CLOSED:  # ...and we expected it to close -> all good
                self._garage_state.complete_transition()
            else:  # -> we expected it to open; not good - something is broken (either door stuck or sensors inverted)
                self._garage_state.abort_transition(error=True)
                self._create_state_issue("closed_when_opening")

            assert self._transition_timer
            self._transition_timer()
            self.async_write_ha_state()
            return

        # sensor indicated the door is not fully closed anymore, and it is in motion
        if self._garage_state.target_state != DoorState.OPENED:  # ...but we didn't expect it to start opening!
            self._garage_state.abort_transition(error=True)
            self._create_state_issue("opened_when_closing")
            self.async_write_ha_state()

    @callback
    async def on_opened_sensor_state_change(self, event: Event) -> None:
        """Triggers when door-fully-open sensor changes its state"""
        self.read_opened_sensor(event.data.get('new_state').state)
        self._ensure_no_sensor_state_conflict()

        if not self._garage_state.is_in_motion():  # door was opened or closed externally
            state = DoorState.OPENED if self._sensor_opened and self._sensor_closed is not False else DoorState.CLOSED
            self._garage_state.force_state(state)
            _LOGGER.debug(f"{self.unique_id} opened sensor tripped when not in motion - computed {state}")
            self.async_write_ha_state()
            return

        if self._sensor_opened:  # sensor indicates that the door has opened
            if self._garage_state.target_state == DoorState.OPENED:  # ...and we expected it to open -> all good
                self._garage_state.complete_transition()
            else:  # -> we expected it to close; not good - something is broken (either door stuck or sensors inverted)
                self._garage_state.abort_transition(error=True)
                self._create_state_issue("opened_when_closing")

            assert self._transition_timer
            self._transition_timer()
            self.async_write_ha_state()
            return

        # sensor indicated the door is not fully opened anymore, and it is in motion
        if self._garage_state.target_state != DoorState.CLOSED:  # ...but we didn't expect it to start closing!
            self._garage_state.abort_transition(error=True)
            self._create_state_issue("closed_when_opening")
            self.async_write_ha_state()

    @callback
    async def on_toggle_state_change(self, event: Event) -> None:
        """Triggered when garage toggle button controller changes its state"""
        event_state = self.value_to_bool(event.data.get('new_state').state)
        _LOGGER.debug(f"{self.unique_id} detected action controller state transition to {event_state}")
        if self._toggle_state == event_state:  # ignore - we triggered it via _toggle_pulse()
            _LOGGER.debug(f"{self.unique_id} transition state is the same as _toggle_state - ignoring")
            return

        # we're DELIBERATELY ignoring transition to "off" state. This can be either the external relay automatically
        # turning off without HA prompting it to do so (safety feature)
        if not event_state:
            _LOGGER.debug(f"{self.unique_id} transition to off - ignoring")
            return

        # since the toggle turned on outside our integration (either from another HA automation or e.g. via native
        # app for a relay or similar) we have no choice other than derive the state
        if self._garage_state.is_in_motion():  # pressing the button will stop the door
            if self._transition_timer is not None:
                self._transition_timer()
            self._garage_state.abort_transition()
            self.async_write_ha_state()
            return

        # if it was FULLY closed (i.e. not opened nor partially) opened we assume transition to open
        _LOGGER.info(f"{self.unique_id} action controller triggered without internal motion - deriving state")
        await self._do_transition_state(DoorState.OPENED if self.is_closed else DoorState.CLOSED)
        self.async_write_ha_state()

    @callback
    async def on_transition_timer_finish(self, _now: datetime) -> None:
        """Handles finishing of the state transition timer running for maximum amount of time expected for transition"""
        _LOGGER.debug(f"{self.unique_id} hit transition timer")
        self._transition_timer = None

        if not self._garage_state.is_in_motion():
            _LOGGER.error(f"Got a timer finish trigger when not in motion. "
                          f"This is a bug in the {self.platform.platform_name} integration")
            return

        # The users can use one or two sensors for homing. If just one was installed (e.g. closed one) the other state
        # will be derived from the time. While not perfect, this isn't an error condition. If we have a sensor for the
        # state, and we hit the timer it means the door got stuck on the way.
        if self._garage_state.target_state == DoorState.OPENED and self._sensor_opened is None:
            # edge case: timer for opening ran out, we have no door-opened sensor, but we have door-closed sensor and
            # the sensor is still indicating "door closed". This means the door never moved and it's still fully closed.
            if self._sensor_closed is not None and self._sensor_closed:
                self._garage_state.force_state(DoorState.CLOSED, error=True)
                self._create_state_issue("closed_after_opening", severity=ir.IssueSeverity.ERROR)
            else:
                _LOGGER.debug(f"{self.unique_id} has no sensor for fully opened - completing on timer")
                self._garage_state.complete_transition()

            self.async_write_ha_state()
            return

        elif self._garage_state.target_state is DoorState.CLOSED and self._sensor_closed is None:
            # edge case: timer for closing ran out, we have no door-closed sensor, but we have door-opened sensor and
            # the sensor is still indicating "door opened". This means the door never moved and it's still fully opened.
            if self._sensor_opened is not None and self._sensor_opened:
                self._garage_state.force_state(DoorState.CLOSED, error=True)
                self._create_state_issue("open_after_closing", severity=ir.IssueSeverity.ERROR)
            else:
                _LOGGER.debug(f"{self.unique_id} has no sensor for fully closed - completing on timer")
                self._garage_state.complete_transition()

            self.async_write_ha_state()
            return

        _LOGGER.warning(f"{self.unique_id} door took longer than expected to " 
                        f"complete transition to {self._garage_state.target_state.name} or got stuck")
        self._garage_state.abort_transition(True)
        self.async_write_ha_state()

    def read_opened_sensor(self, raw_value: str | None = None) -> None:
        self._sensor_opened = self._do_read_binary_state(self._garage_state.controller.opened_sensor, raw_value,
                                                         not self._garage_state.controller.on_open)

    def read_closed_sensor(self, raw_value: str | None = None) -> None:
        self._sensor_closed = self._do_read_binary_state(self._garage_state.controller.closed_sensor, raw_value,
                                                         not self._garage_state.controller.on_close)

    def _sync_state(self) -> None:
        """Attempts to derive initial state of the door from sensors"""
        if self._ensure_no_sensor_state_conflict():
            return

        if self._sensor_opened:
            self._garage_state.last_state = DoorState.OPENED
            return

        if self._sensor_closed:
            self._garage_state.last_state = DoorState.CLOSED
            return

        # If none of the sensors are tripped we hope that at least one sensor is present. In such a condition we can
        # wait the time normally needed to close or open the cover. We don't need a separate timer here, as we're
        # observing sensors anyway. Until then, we should let the user know that the state of the door is unknown.

    def _ensure_no_sensor_state_conflict(self) -> bool:
        """Ensures unrealistic sensor reading aren't present (i.e. door open and closed at the same time)"""
        if self._sensor_opened and self._sensor_closed:
            self._create_state_issue("open_and_closed", ir.IssueSeverity.CRITICAL)
            return True

        return False

    def _create_state_issue(self, state: str, severity: ir.IssueSeverity = ir.IssueSeverity.WARNING) -> None:
        _LOGGER.error(f"{self.unique_id} door error \"{state}\"")
        ir.async_create_issue(self.hass, DOMAIN, f"{self.unique_id}_{state}", is_fixable=True, severity=severity,
                              translation_key=state)

    def _do_read_binary_state(self, sensor_id: str | None, known_value: str | None = None,
                              invert: bool = False) -> bool:
        """Read sensor or switch state and normalize it to a binary form"""
        assert sensor_id is not None

        if known_value is None:
            state = self.hass.states.get(sensor_id)
            if state is None:
                return False
            known_value = state.state

        value = not self.value_to_bool(known_value) if invert else self.value_to_bool(known_value)
        _LOGGER.debug(f"{self.unique_id} read {sensor_id} sensor raw={known_value} transform={value}")

        return value

    @staticmethod
    def value_to_bool(state: bool | str | int | float) -> bool:
        if type(state) is bool:
            return state

        if isinstance(state, (int, float)):
            return state > 0

        try:
            return float(state) > 0
        except (ValueError, TypeError):
            pass

        return len(state) > 0 and (state.lower() == 'on' or state[0].lower() == 't')
