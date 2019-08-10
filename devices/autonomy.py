from src.common.coord import *


MIN_DESTINATION_DIST = 0.5


class Autonomy:
	def __init__(self):
		self.running = False
		self.waypoints = []
		self.next_waypoint = 0

	def set_waypoints(self, waypoints):
		self.waypoints = waypoints

	def start(self, starting_waypoint = 0):
		if starting_waypoint < 0:
			self.running = False
			return

		self.running = True
		self.next_waypoint = starting_waypoint

	def halt(self):
		self.running = False

	def is_running(self):
		return self.running

	def get_status(self):
		str_running = 'in progress' if self.running else 'idle'
		str_progress = '{} out of {}'.format(
			self.next_waypoint,
			len(self.waypoints)
		)
		return '{}; {}'.format(str_running, str_progress)

	def get_command(self, position, heading):
		'''
		Input: position as (latitude, longitude), heading in radians
		Returns pair (throttle, turning speed)
		'''
		if not self.is_running():
			print('[auto] not running!')
			return (0, 0)

		if self.next_waypoint >= len(self.waypoints):
			self.halt()
			print('[auto] next_waypoints >= len(waypoints)')
			return (0.0)

		next_waypoint = self.waypoints[self.next_waypoint]
		x, y = relative_xy(origin=position, destination=next_waypoint)
		x, y = (
			x * math.cos(heading) - y * math.sin(heading),
			x * math.sin(heading) + y * math.cos(heading)
		)

		dist = math.sqrt(x * x + y * y)
		if dist <= MIN_DESTINATION_DIST:
			self.next_waypoint += 1
			if self.next_waypoint >= len(self.waypoints):
				self.halt()
			print('[auto] reached the next waypoint')
			return (0, 0)

		heading_to_dist = 90 - math.degrees(math.atan2(y, x))
		while heading_to_dist < -180:
			heading_to_dist += 360
		while heading_to_dist > 180:
			heading_to_dist -= 360

		# TODO use a pid (?)
		if heading_to_dist <= -45:
			return (0.0, -0.3)
		elif heading_to_dist >= 45:
			return (0.0, 0.3)
		else:
			turning = 0.3 * (heading_to_dist / 45)
			return (0.4, turning)


def main():
	import cv2
	import numpy as np

	import time


	IMG_WIDTH = 800
	ORIGIN = (53.015963, 18.589058)
	LAT_RANGE = 0.0015
	LON_RANGE = 0.0025

	POS_RATE = 30.0
	HEADING_RATE = 80.0


	pos = ORIGIN
	heading = 213.0

	waypoints = [
		(53.0165, 18.589058),
		(53.0160, 18.590),
		(53.0155, 18.588),
		(53.0160, 18.589)
	]

	a = Autonomy()
	a.set_waypoints(waypoints)
	a.start()

	def to_xy(pos):
		lat, lon = pos
		x = ((lon - ORIGIN[1]) / LON_RANGE) + 0.5
		y = ((lat - ORIGIN[0]) / LAT_RANGE) + 0.5
		x_pix = IMG_WIDTH * x
		y_pix = IMG_WIDTH * (1 - y)
		return x_pix, y_pix

	t = time.time()
	while True:
		nt = time.time()
		dt = nt - t
		t = nt

		# simulation
		print('position: {:2.8f}° {:2.8f}°'.format(*pos))
		print('heading:  {:3.2f}°'.format(heading))

		throttle, turning = a.get_command(pos, heading)

		heading += dt * HEADING_RATE * turning
		if heading < 0:
			heading += 360
		if heading > 360:
			heading -= 360

		dist = dt * POS_RATE * throttle
		phi = math.radians(90 - heading)
		dx, dy = dist * math.cos(phi), dist * math.sin(phi)
		pos = move(pos, (dx, dy))

		# visualization
		img = np.zeros((IMG_WIDTH, IMG_WIDTH, 3), dtype=np.uint8)
		for p in waypoints:
			x, y = to_xy(p)
			cv2.circle(img, (round(x), round(y)), 5, (255, 255, 0), -1)

		px, py = to_xy(pos)
		cv2.circle(img, (round(px), round(py)), 7, (0, 255, 255), -1)

		cv2.imshow('simulation', img)
		if cv2.waitKey(1) == 27:
			break


if __name__ == '__main__':
	main()
