"""Config flow for Up-Smart Garage integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector

from .const import *

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Up-Smart Garage."""
    VERSION = 1
    data_schema = {
        vol.Required(CONF_NAME, default=ATTR_NAME): str,
        vol.Required(CONF_TOGGLE_RELAY): selector({
            "entity": {
                "filter": {"domain": ["switch", "input_boolean"]}
            }
        }),

        vol.Optional(CONF_CLOSED_SENSOR): selector({
            "entity": {
                "filter": {"domain": ["binary_sensor", "sensor"]}
            }
        }),
        vol.Required(CONF_INVERT_CLOSED_SENSOR, default=False): bool,
        vol.Required(CONF_CLOSE_TIME): selector({"duration": {}}),

        vol.Optional(CONF_OPENED_SENSOR): selector({
            "entity": {
                "filter": {"domain": ["binary_sensor", "sensor"]}
            }
        }),
        vol.Required(CONF_INVERT_OPENED_SENSOR, default=False): bool,
        vol.Required(CONF_OPEN_TIME): selector({"duration": {}}),
    }

    def _create_form_schema(self) -> vol.Schema:
        return vol.Schema(self.data_schema)

    async def validate_input(self, hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the user input"""
        # todo: validate things like close time >0 etc

        _LOGGER.info(data)
        _LOGGER.info(data[CONF_CLOSE_TIME])
        close_time = time_to_seconds(data[CONF_CLOSE_TIME])
        _LOGGER.info(close_time)
        if close_time <= 0:
            raise InvalidCloseTime("Time to close must be over 0s")

        open_time = time_to_seconds(data[CONF_OPEN_TIME])
        if open_time <= 0:
            raise InvalidOpenTime("Time to open must be over 0s")

        if CONF_OPENED_SENSOR not in data and CONF_CLOSED_SENSOR not in data:
            raise SensorRequired("At least one sensor is required")

        return data

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self._create_form_schema())

        # await self.async_set_unique_id(device_unique_id)
        # self._abort_if_unique_id_configured()
        errors = {}
        try:
            _LOGGER.debug('Up-Smart Garage form submitted - validating data')
            info = await self.validate_input(self.hass, user_input)
        except SensorRequired as e:
            _LOGGER.exception(f"Sensor not configured: {str(e)}")
            errors["base"] = "sensor_required"
        except InvalidOpenTime as e:
            _LOGGER.exception(f"Invalid open time: {str(e)}")
            errors["base"] = "invalid_open_time"
        except InvalidCloseTime as e:
            _LOGGER.exception(f"Invalid close time: {str(e)}")
            errors["base"] = "invalid_close_time"
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.exception(f"Unexpected exception: {str(e)}")
            errors["base"] = "unknown"
        else:
            _LOGGER.info('Configured Up-Smart Garage with data:')
            _LOGGER.info(user_input)
            return self.async_create_entry(title=info['name'], data=user_input)

        _LOGGER.error('Up-Smart Garage form validation failed')
        return self.async_show_form(step_id="user", data_schema=self._create_form_schema(), errors=errors)


def time_to_seconds(time: dict) -> int:
    seconds = 0

    if 'seconds' in time:
        seconds += time['seconds']

    if 'minutes' in time:
        seconds += time['minutes'] * 60

    if 'hours' in time:
        seconds += time['hours'] * 3600

    return seconds


class SensorRequired(HomeAssistantError):
    """At least one sensor is required"""


class InvalidOpenTime(HomeAssistantError):
    """Time to open needs to be set"""


class InvalidCloseTime(HomeAssistantError):
    """Time to close needs to be set"""
