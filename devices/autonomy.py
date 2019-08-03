from devices.coord import *


MIN_DESTINATION_DIST = 2.0


class Autonomy:
	def __init__(self):
		self.running = False
		self.waypoints = []
		self.next_waypoint = 0

	def set_waypoints(self, waypoints):
		self.waypoints = waypoints

	def start(self, starting_waypoint = 0):
		self.running = True
		self.next_waypoint = starting_waypoint

	def halt(self):
		self.running = False

	def is_running(self):
		return self.running

	def get_command(self, position, heading):
		'''
		Returns pair (throttle, turning speed)
		'''
		if not self.is_running():
			return (0, 0)

		next_waypoint = self.waypoints[self.next_waypoint]
		x, y = relative_xy(origin=position, destination=next_waypoint)
		x, y = (
			x * math.cos(math.radians(heading)) - y * math.sin(math.radians(heading)),
			x * math.sin(math.radians(heading)) + y * math.cos(math.radians(heading))
		)

		dist = math.sqrt(x * x + y * y)
		if dist <= MIN_DESTINATION_DIST:
			self.next_waypoint += 1
			if self.next_waypoint == len(self.waypoints):
				self.is_running = False
			return (0, 0)

		heading_to_dist = math.atan2(y, x)

		# TODO use a pid (?)
		if heading_to_dist <= math.pi / 4
			return (0.1, 1)
		elif heading_to_dist >= math.pi / 4:
			return (0.1, -1)
		else:
			turning = -(heading_to_dist / (math.pi / 4))
			return (0.4, turning)


if __name__ == '__main__':
	# TODO run simple simulation
	pass
