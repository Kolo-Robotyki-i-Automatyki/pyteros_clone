import math
import numpy as np
import time
import threading

from devices.rover import arm_lower, arm_upper, arm_rot, grip_lat
from devices.zeromq_device import DeviceWorker, DeviceInterface, remote, include_remote_methods
from src.common.coord import *
from src.common.misc import *


EPSILON = 0.000001

MAX_SPEED_MPS = 1.5
ROVER_WIDTH_M = 0.8
DRIVE_COMMAND_TIMEOUT_S = 0.2

SIMULATION_PERIOD = 0.01


class FakeRoverWorker(DeviceWorker):
    def __init__(self, req_port, pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

        self.sim_lock = None

        self.coordinates = (0.0, 0.0)
        self.heading = 0.0
        self.last_sim_update = time.perf_counter()
        
        self.turning = 0.0
        self.throttle = 0.0
        self.wheels_power = {
            'left': 0.0,
            'right': 0.0,
        }
        self.wheels_last_received_command = time.perf_counter()

        self.rover_reversed = False

    def init_device(self):
        self.sim_lock = threading.Lock()
        self.start_timer(self._sim_step, SIMULATION_PERIOD)

    def status(self):
        status_d = super().status()
        
        status_d.update({
            'connected': True,
            'position': self.get_position(),
            'coordinates': self.get_coordinates(),
        })
        
        with self.sim_lock:
            status_d.update({
                'heading': self.get_orientation(),
                'encoders': self.get_encoders(),
                'index_pulses': self.get_index_pulses(),
                'air_temperature': self.get_air_temperature(),
                'air_humidity': self.get_air_humidity(),
                'battery': 69.0,
                'wheels_power': self.wheels_power,
            })

        return status_d

    def _sim_step(self):
        time_now = time.perf_counter()
        dt = time_now - self.last_sim_update
        self.last_sim_update = time_now

        if time_now - self.wheels_last_received_command >= DRIVE_COMMAND_TIMEOUT_S:
            self.wheels_power = {
                'left': 0.0,
                'right': 0.0,
            }
            return

        with self.sim_lock:
            heading = self.heading
            dir_vec = np.array([math.sin(heading), math.cos(heading)])

            pos_xy = np.array(self.get_position())
            pos_xy_l = pos_xy + np.array([
                (ROVER_WIDTH_M / 2.0) * math.sin(heading - 0.5 * math.pi),
                (ROVER_WIDTH_M / 2.0) * math.cos(heading - 0.5 * math.pi)
            ])
            pos_xy_r = pos_xy + np.array([
                (ROVER_WIDTH_M / 2.0) * math.sin(heading + 0.5 * math.pi),
                (ROVER_WIDTH_M / 2.0) * math.cos(heading + 0.5 * math.pi)
            ])

            left, right = self.wheels_power['left'], self.wheels_power['right']

            new_pos_xy_l = pos_xy_l + dir_vec * (dt * MAX_SPEED_MPS) * left
            new_pos_xy_r = pos_xy_r + dir_vec * (dt * MAX_SPEED_MPS) * right

            x, y = (new_pos_xy_l + new_pos_xy_r) / 2.0
            dx, dy = x - pos_xy[0], y - pos_xy[1]

            new_heading = math.atan2(new_pos_xy_r[0] - new_pos_xy_l[0], new_pos_xy_r[1] - new_pos_xy_l[1]) - (0.5 * math.pi)

            self.heading = new_heading
            self.coordinates = move(self.coordinates, (dx, dy))

    @remote
    def read(self):
        pass

    @remote
    def set_pid_wheels(self, on=True, params = None):
        pass

    @remote
    def set_blink(self, on = 1):
        pass

    @remote
    def get_coordinates(self):
        return self.coordinates

    @remote
    def get_orientation(self):
        return self.heading + (math.pi if self.rover_reversed else 0.0)

    @remote
    def get_position(self, origin=(0, 0), axis=-1):
        x, y = relative_xy(origin, self.get_coordinates())
        if axis == 0:
            return x
        elif axis == 1:
            return y
        else:
            return (x, y)

    @remote
    def abort_script(self):
        pass

    @remote
    def run_script(self, code):
        pass

    @remote
    def is_script_running(self):
        return False

    @remote
    def get_cmd_stream_port(self):
        return 0

    @remote
    def fix_pos(self, x, y):
        pass

    @remote
    def servo(self, id, move):
        pass

    @remote
    def servo_pos(self, id, pos):
        pass

    @remote
    def servos(self):
        return [("servo_306:" + str(i%8), i) for i in range(0, 8)] + \
               [("servo_305:" + str(i%8), i) for i in range(8, 16)] + \
               [("servo_307:" + str(i%8), i) for i in range(16, 24)] + \
               [("arm_upper: 100", 100), ("grip_clamp: 101", 101)]

    @remote
    def tags(self):
        return []

    @remote
    def slope_points(self):
        return []

    @remote
    def tacho(self):
        return 0.0

    @remote
    def send(self, id, data):
        pass

    @remote
    def start_ik(self):
        pass

    @remote
    def apply_index(self):
        pass

    @remote
    def get_encoders(self):
        return {}

    @remote
    def get_index_pulses(self):
        return {}

    @remote
    def set_ik(self, on = True):
        pass

    @remote
    def ik_deg(self, tx, ty, ta, td):
        pass

    @remote
    def ik(self, params):
        pass

    @remote
    def ik_arm(self, params):
        pass

    @remote
    def ik_rover(self, params):
        pass

    @remote
    def power(self, id, power):
        pass

    @remote
    def update_script_library(self, library):
        pass

    @remote
    def drive(self, axis, power):
        if axis == 0:  # throttle
            self.throttle = power
        if axis == 1:  # turning
            self.turning = power
        
        if abs(self.throttle) + abs(self.turning) > EPSILON:
            self.wheels_last_received_command = time.perf_counter()

        left = self.throttle + self.turning
        right = self.throttle - self.turning

        if not self.rover_reversed:
            self.wheels_power = {
                'left': left,
                'right': right,
            }
        else:
            self.wheels_power = {
                'left': right,
                'right': left,
            }

    @remote
    def drive_both_axes(self, throttle, turning):
        self.drive(0, throttle)
        self.drive(1, turning)

    @remote
    def axes(self):
        return [
            ("wheels_left", 129),
            ("wheels_right", 130),
            ("arm_rot", arm_rot),
            ("arm_lower", arm_lower),
            ("arm_upper", arm_upper),
            ("grip_lat", grip_lat),
            ("grip_rot", 192),
            ("grip_clamp", 193),
            ("blinker", 210)
        ] + [
            ("arm_ik_forward", 2000),
            ("arm_ik_up", 2001),
            ("arm_ik_grip", 2002),
            ("arm_ik_left", 2003)
        ] + [
            ("wheel_" + str(i - 140), i) for i in range(140, 144)
        ] + [
            ("", i) for i in range(185, 200)
        ] + [
            ("", i) for i in range(202, 210)
        ]

    @remote
    def get_air_temperature(self):
        return 0.0

    @remote
    def get_air_humidity(self):
        return 0.0

    @remote
    def get_available_devices(self):
        return []

    @remote
    def reset_available_devices(self):
        pass

    @remote
    def set_rover_reversed(self, reversed = True):
        self.rover_reversed = reversed


@include_remote_methods(FakeRoverWorker)
class FakeRover(DeviceInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def createDock(self, parentWidget, menu=None):
        pass
