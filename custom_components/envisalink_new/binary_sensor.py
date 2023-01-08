"""Support for Envisalink zone states- represented as binary sensors."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .models import EnvisalinkDevice
from .const import (
    DOMAIN,
    LOGGER,
    CONF_NUM_ZONES,
    SIGNAL_ZONE_UPDATE,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    controller = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for zone_num in range(1, entry.data[CONF_NUM_ZONES] + 1):
        entity = EnvisalinkBinarySensor(
            hass,
            zone_num,
            controller,
        )
        entities.append(entity)

    async_add_entities(entities)


class EnvisalinkBinarySensor(EnvisalinkDevice, BinarySensorEntity):
    """Representation of an Envisalink binary sensor."""

    def __init__(self, hass, zone_number, controller):
        """Initialize the binary_sensor."""
        self._zone_type = BinarySensorDeviceClass.OPENING # TODO
        self._zone_number = zone_number
        name_suffix = f"zone_{self._zone_number}"
        self._attr_unique_id = f"{controller.unique_id}_{name_suffix}"

        LOGGER.debug("Setting up zone: %s", name_suffix)
        super().__init__(name_suffix, controller)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ZONE_UPDATE, self.async_update_callback
            )
        )

    @property
    def _info(self):
        return self._controller.controller.alarm_state["zone"][self._zone_number]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}

        # The Envisalink library returns a "last_fault" value that's the
        # number of seconds since the last fault, up to a maximum of 327680
        # seconds (65536 5-second ticks).
        #
        # We don't want the HA event log to fill up with a bunch of no-op
        # "state changes" that are just that number ticking up once per poll
        # interval, so we subtract it from the current second-accurate time
        # unless it is already at the maximum value, in which case we set it
        # to None since we can't determine the actual value.

        seconds_ago = self._info["last_fault"]
        if seconds_ago < 65536 * 5:
            now = dt_util.now().replace(microsecond=0)
            delta = datetime.timedelta(seconds=seconds_ago)
            last_trip_time = (now - delta).isoformat()
        else:
            last_trip_time = None

        attr[ATTR_LAST_TRIP_TIME] = last_trip_time

        # Expose the zone number as an attribute to allow
        # for easier entity to zone mapping (e.g. to bypass
        # the zone).
        attr["zone"] = self._zone_number

        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._info["status"]["open"]

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

    @callback
    def async_update_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self.async_write_ha_state()
