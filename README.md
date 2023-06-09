# Up-Smart Garage

Upgrade your garage and make it smarter!


### Challenge

Garage openers are mostly dumb motors, exposing only a single toggle button that performs three functions at once:
 - raise/open the door
 - lower/close the door
 - stop the door when it's moving

This apparent simplicity however, means there's no feedback about the state. In addition, obstruction cannot be reported
either. The more you start thinking about possible edge cases (what if the door stopped? what if someone opened it with 
a remote? ~~what if a meteorite struck the motor?~~), the more you realize it's not as simple as it seems.

### I want a simple garage in HA!

The basic control nature of most garage doors makes them ostensibly simple to automate, but just on the surface. In the 
simplest form, a [HomeAssistant cover template](https://www.home-assistant.io/integrations/cover.template/#garage-door) 
can be used to achieve a simple operation. However, if you want:

 - obstruction detection
 - open/close/stop that actually works
 - real and simulated reporting of open/close state
 - support for state detection when doors are operated manually
 - position reporting
 - long-term performance statistics to detect issues before they happen
 - ...and probably more

...you really need a custom component.


### What do I need to make it work?

You need, at minimum:

 - A relay to bridge garage opener toggle button
 - A reed sensor near the edge of the door

Then, add an integration and select correct entities as prompted by HA - no JSON editing needed :)


### How does it work?
The idea for the component is hardly revolutionary. Internally, the custom component relies on at least one sensor 
reporting door being fully closed or fully opened, and some clever timers. It originally started as a VERY overgrown
automation, that was not maintainable.

It is recommended that you mount the reed sensor so that it detects the door being fully closed. The code will then
simulate door open state with a timer. The code is smart enough to report jams even with one sensor, but it's limited, 
as it can only know if the door moved (but not how far it did). With two sensors, one reporting door-fully-closed and
one reporting door-fully-opened a complete jamming detection is possible.

The code tries to always fail-safe, i.e. if it's not 100% sure the door is closed it will report it as at least 
partially open to alert you about a possible danger. In addition, the code also ensures that toggle relay isn't held for
too long (but you should still ensure safety on the hardware level).



#### Inspirations

This project was inspired by the following threads:
 - https://community.home-assistant.io/t/faking-garage-door-states-like-closing-opening/276691
 - https://community.home-assistant.io/t/garage-door-opened-timer/233081
 - https://community.home-assistant.io/t/solved-garage-cover-based-on-timer-no-open-close-state-sensor/79683
 - https://community.home-assistant.io/t/shelly-1-garage-door-controller/209917