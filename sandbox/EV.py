"""
evread/readout is too complicated and might not synchronize well with the game loop.
This here is a python native program. A full rotation of the wheel corresponds roughly to 18000 pixels.

class evtrack(query="G703")

Usage
-----
An instance of evtrack object reads and accumulates all the displacements on the y-axis of the mouse for position tracking.
Invoking evtrack.acc() returns the total accumulated pixel displacements and resets the accumulator.

Run EV.calibrate() to help with gain calibration.
"""

import evdev
import threading

class evtracker():
  def __init__(self, query="G703"):
    self._y = 0
    self._lock = threading.Lock()

    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    devices = [device for device in devices if query in device.name]
    print("Reading from following devices:")
    for device in devices:
      print(device.path, device.name, device.phys)

    self.threads = [threading.Thread(target=self.pos, args=(device,), daemon=True) for device in devices]
    for t in self.threads:
      t.start()

  def acc(self):
    with self._lock:
      y = self._y
      self._y = 0
    return y

  def pos(self, device):
    for event in device.read_loop():
      if event.type == evdev.ecodes.EV_REL and event.code == 0:
        with self._lock:
          self._y -= event.value


def calibrate():
  """
  1. Position the wheel at the red marker,
  2. Execute this function,
  3. Turn the bloody wheel 10 times (or whatever),
  4. Read the value and divide by total number of turns.
  """
  import time
  tracker = evtracker()
  acc = 0
  while True:
    acc += tracker.acc()
    print(acc)
    time.sleep(.001)
