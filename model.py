from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import time
import logging
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__package__)

class DoorState(Enum):
    CLOSED = 0
    OPENED = 1
    PARTIALLY_OPEN = 2


@dataclass
class StateController:
    toggle_controller: str

    closed_sensor: str | None
    on_close: bool
    open_to_close_delta: float

    opened_sensor: str | None
    on_open: bool
    close_to_open_delta: float

    pulse_time: float

    def __init__(self, controller: str, closed_sensor: str | None, close_time: int | float, opened_sensor: str | None,
                open_time: int | float):
        self.toggle_controller = controller
        self.closed_sensor = closed_sensor
        self.on_close = True
        self.opened_sensor = opened_sensor
        self.on_open = True
        self.pulse_time = 1.5  # todo: I'm not sure if this needs to be user-configurable?

        if close_time <= 0:
            raise ValueError(f"Close time must be a positive number (got \"{close_time}\")")
        if open_time <= 0:
            raise ValueError(f"Open time must be a positive number (got \"{open_time}\")")

        self.open_to_close_delta = close_time
        self.close_to_open_delta = open_time

    def invert_closed_signal(self, inverted: bool = True) -> None:
        self.on_close = not inverted

    def invert_opened_signal(self, inverted: bool = True) -> None:
        self.on_open = not inverted


@dataclass
class GarageDoorState:
    internal_id: str
    controller: StateController
    last_state: DoorState | None  # if None it means that state cannot be determined
    target_state: DoorState | None  # if None it means the state isn't in progress
    transition_triggered: float | None
    error: bool

    def __init__(self, int_id: str, controller: StateController, current_tate: DoorState | None = None):
        self.internal_id = int_id
        self.controller = controller
        self.last_state = current_tate
        self.target_state = None
        self.transition_triggered = None
        self.error = False

    @property
    def delta_for_current_state(self) -> float:
        if self.target_state is None:  # not in motion
            return 0

        return self.controller.close_to_open_delta if self.target_state == DoorState.OPENED \
            else self.controller.open_to_close_delta

    def transition(self, target: DoorState) -> None:
        assert target is not None
        if self.last_state is target:
            raise ValueError(
                f"Current ({self.last_state.name}) and target ({target.name}) states are the same")

        self.target_state = target
        self.transition_triggered = time.monotonic()

    def complete_transition(self) -> None:
        if self.target_state is None:
            raise ValueError("There is no transition in progress")

        self.force_state(self.target_state)

    def abort_transition(self, error: bool = False) -> None:
        if self.target_state is None:
            raise ValueError("There is no transition in progress")

        self.force_state(DoorState.PARTIALLY_OPEN, error)

    def force_state(self, state: DoorState, error: bool = False) -> None:
        self.last_state = state
        self.target_state = None
        self.transition_triggered = None
        self.error = error

    def is_in_motion(self) -> bool:
        _LOGGER.debug(f"isInMotion? target={self.target_state} state={self.target_state is not None}")
        return self.target_state is not None
