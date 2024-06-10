import numpy as np

res = (int(540/6), int(960/6/2))
view = (60, 960*60/540/2)
centres = [-120, -60, 0, 60, 120]

def s2c(lon, lat, lon0, lat0):
  c = np.cos(lat) * np.cos(lon - lon0)
  x = np.cos(lat) * np.sin(lon - lon0) / c
  y = np.sin(lat) / c
  return x, y

x = np.array([-view[0] / 2 / 360 * 2 * np.pi, view[0] / 2 / 360 * 2 * np.pi])
y = np.array([-view[1] / 2 / 360 * 2 * np.pi, view[1] / 2 / 360 * 2 * np.pi])
x, y = s2c(x, y, 0.0, 0.0)
y_range = y[1]
x = np.linspace(x[0], x[1], res[0])
y = np.linspace(y[0], y[1], res[1])

cx, cy = np.meshgrid(x, y)

f = open("test.data", "w")
f.write("2\n")
f.write("{} {}\n".format(res[0] * len(centres), res[1]))

for c in centres:
  for x, y in zip(cx.flatten(), cy.flatten()):
    rho = np.sqrt(x**2 + y**2)
    c = np.arctan(rho)
    lon = np.arctan(x * np.sin(c) / (rho * np.cos(c)))
    lat = np.arcsin(y * np.sin(c) / rho)
    if np.isnan(lon) or np.isnan(lat):
      continue
    lon = (lon + np.pi + c / 360 * 2 * np.pi) % (2 * np.pi) / 2 / np.pi
    lat = (lat + np.pi/2) % (2 * np.pi) / np.pi
    f.write("{} {} {} {} 1\n".format((x + c / 360 * 2 * np.pi) / y_range, y / y_range, lon, lat))

f.close()
