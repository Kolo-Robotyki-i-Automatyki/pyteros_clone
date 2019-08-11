from src.common.coord import *

from enum import IntEnum
import time


MIN_DESTINATION_DIST = 0.5
MIN_SCRIPT_WAIT_TIME = 10.0


class Task(IntEnum):
	DRIVE_TO = 1
	RUN_SCRIPT = 2

class State(IntEnum):
	IDLE = 1
	GET_NEXT_TASK = 2

	DRIVE_TO = 10
	LAUNCH_SCRIPT = 11
	SLEEP = 12
	WAIT_FOR_SCRIPT_COMPLETION = 13

class Command(IntEnum):
	NOP = 1
	SET_THROTTLE_TURNING = 2
	RUN_SCRIPT = 3


class AutoInput:
	def __init__(self, position, heading: float, script_running: bool):
		self.position = position
		self.heading = heading
		self.script_running = script_running


class Autonomy:
	def __init__(self):
		self.halt()
		self.tasks = []
		self.next_task = 0

		self.debug_status = {}

	def is_running(self):
		return self.state != State.IDLE

	def set_tasks(self, tasks):
		self.tasks = tasks

	def start(self, starting_task: int = 0):
		if starting_task < 0:
			self.halt()
			return

		self.state = State.GET_NEXT_TASK
		self.params = None
		self.next_task = starting_task

	def halt(self):
		self.state = State.IDLE
		self.params = None
		self.next_task = 0

	def get_status(self):
		status = { 'state': (str(self.state), str(self.params)) }
		status['tasks'] = [str(task) for task in self.tasks]
		status['next_task'] = self.next_task

		status.update(self.debug_status)

		return status

	def get_command(self, auto_input: AutoInput):
		self.debug_status = {}

		func = {
			State.IDLE: self._auto_idle,
			State.GET_NEXT_TASK: self._auto_get_next_task,
			State.DRIVE_TO: self._auto_drive_to,
			State.LAUNCH_SCRIPT: self._auto_launch_script,
			State.WAIT_FOR_SCRIPT_COMPLETION: self._auto_wait_for_script_completion,
		}[self.state]

		try:
			command = func(auto_input	)
		except Exception as e:
			self.debug_status['exception'] = str(e)
			command = Command.NOP, []

		self.debug_status['last_command'] = str(command)

		return command

	def _auto_idle(self, auto_input):
		return Command.NOP, []

	def _auto_get_next_task(self, auto_input):
		if self.next_task >= len(self.tasks):
			self.halt()
		else:
			task, args = self.tasks[self.next_task]
			if task == Task.DRIVE_TO:
				self.state = State.DRIVE_TO
			elif task == Task.RUN_SCRIPT:
				self.state = State.LAUNCH_SCRIPT
			self.params = args
			self.next_task += 1
		return Command.NOP, []

	def _auto_drive_to(self, auto_input):
		next_waypoint = self.params
		position = auto_input.position
		heading = auto_input.heading

		x, y = relative_xy(origin=position, destination=next_waypoint)
		x, y = (
			x * math.cos(heading) - y * math.sin(heading),
			x * math.sin(heading) + y * math.cos(heading)
		)

		dist = math.sqrt(x * x + y * y)
		if dist <= MIN_DESTINATION_DIST:
			print('[auto] reached the next waypoint')
			self.state = State.GET_NEXT_TASK
			self.params = None
			return Command.NOP, []

		heading_to_dist = 90 - math.degrees(math.atan2(y, x))
		while heading_to_dist < -180:
			heading_to_dist += 360
		while heading_to_dist > 180:
			heading_to_dist -= 360

		self.debug_status['target_x'] = x
		self.debug_status['target_y'] = y
		self.debug_status['heading_to_target'] = heading_to_dist

		# TODO use a pid (?)
		if heading_to_dist <= -45:
			throttle, turning = 0.0, -0.3
		elif heading_to_dist >= 45:
			throttle, turning = 0.0, 0.3
		else:
			turning = 0.3 * (heading_to_dist / 45)
			throttle = 0.4
		return Command.SET_THROTTLE_TURNING, [throttle, turning]

	def _auto_launch_script(self, auto_input):
		script_name = self.params
		
		self.state = State.WAIT_FOR_SCRIPT_COMPLETION
		self.params = time.time()

		return Command.RUN_SCRIPT, [script_name]

	def _auto_wait_for_script_completion(self, auto_input):
		start_time = self.params
		now = time.time()

		if now - start_time < MIN_SCRIPT_WAIT_TIME:
			self.debug_status['time_waiting'] = now - start_time
		else:
			if not auto_input.script_running:
				self.state = State.GET_NEXT_TASK
				self.params = None
			
		return Command.NOP, []


# TODO rewrite this?

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
	# it's outdated
	# main()
	pass
