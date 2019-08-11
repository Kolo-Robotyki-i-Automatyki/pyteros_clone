import math
import re


EARTH_R = 6371000

re_float         = r"(\d+(?:\.\d+)?)"
re_float_signed  = r"(-?\d+(?:\.\d+)?)"
re_int           = r"(\d+)"
re_letter        = r"([NESWnesw])"
re_coord_decimal = re_float_signed
re_coord_dms     = re_int + r"\s*\*\s*" + re_int + r"\s*\'\s*" + re_float + r"\s*\'\'\s*" + re_letter


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


def parse_latitude(lat):
    return parse_coordinate(lat, (0, 90), 'N', 'S')

def parse_longitude(lon):
    return parse_coordinate(lon, (0, 180), 'E', 'W')

def parse_coordinate(coordinate, value_interval, positive, negative):
    try:
        val = None

        match = re.search(re_coord_decimal, coordinate)
        if match is not None:
            groups = match.groups()

            degrees = float(groups[0])
            letter  = positive if degrees >= 0 else negative

            val = abs(degrees)

        match = re.search(re_coord_dms, coordinate)
        if match is not None:
            groups = match.groups()

            degrees = float(groups[0])
            minutes = float(groups[1])
            seconds = float(groups[2])
            letter  = groups[3].upper()

            if minutes < 0 or minutes > 59:
                raise ValueError
            if seconds < 0 or seconds > 59:
                raise ValueError

            val = degrees + (minutes / 60.0) + (seconds / 3600.0)

        if val is None:
            raise ValueError
    except:
        raise ValueError

    min_val, max_val = value_interval
    if val < min_val or val > max_val:
        raise ValueError
    if letter != positive and letter != negative:
        raise ValueError

    if letter == negative:
        val = -val

    return val

def get_coord_from_lineedit(lineedit, is_latitude: bool):
	val_str = lineedit.text()
	if len(val_str) == 0:
		val_str = lineedit.placeholderText()
		if len(val_str) == 0:
			val_str = '0.0'

	val_str = val_str.replace(',', '.')

	try:
		val = float(val_str)
	except:
		try:
			if is_latitude:
				val = parse_latitude(val_str)
			else:
				val = parse_longitude(val_str)
		except:
			val = 0.0

	return val
