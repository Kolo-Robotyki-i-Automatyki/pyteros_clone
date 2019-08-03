import math


EARTH_R = 6371000


def relative_xy(origin, destination):
	'''
	Input: (latitude, longitude) pairs
	Output: relative position in meters
	'''
	d_lat = destination[0] - origin[0]
	d_lon = destination[1] - origin[1]

	x = 2 * math.pi * EARTH_R * (d_lon / 360) * math.cos(math.radians(origin[0]))
	y = 2 * math.pi * EARTH_R * (d_lat / 360)

	return x, y

def move(origin, displacement):
	'''
	Origin is (latitude, longitude), displacement is in meters
	Returns new (latitude, longitude)
	'''
	x, y = displacement
	d_lon = 360 * x / (2 * math.pi * EARTH_R * math.cos(math.radians(origin[0])))
	d_lat = 360 * y / (2 * math.pi * EARTH_R)

	lat = origin[0] + d_lat
	lon = origin[1] + d_lon

	return (lat, lon)
