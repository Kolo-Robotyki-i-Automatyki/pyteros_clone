import collections
import itertools
import math
import queue
import threading
import time
import typing

from devices.misc.xbox import XBOX_AXES
from devices.rover import MoveCommand
from devices.zeromq_device import DeviceWorker, DeviceInterface
from devices.zeromq_device import remote, include_remote_methods

from src.common.misc import *
from src.common.settings import *


EPSILON = 0.00000001
DEADZONE = 0.17
MAX_SMOOTHNESS = 100

RECONNECT_PERIOD_S = 3.0


class VirtualMotor:
    def __init__(self, method: typing.Callable, axis: typing.Optional[int]):
        self.method = method
        self.axis = axis

        self.value = 0.0
        self.last_sent_value = 0.0

    def add(self, val):
        self.value += val

    def execute(self):
        val_now = clamp(self.value, -1.0, 1.0)
        val_then = self.last_sent_value

        self.last_sent_value = self.value
        self.value = 0.0

        if abs(val_now) <= EPSILON and abs(val_now - val_then) <= EPSILON:
            return

        if self.axis is None:
            self.method(val_now)
        else:
            self.method(self.axis, val_now)


class ButtonMapping:
    def __init__(self, gamepad_axis: str, motor: VirtualMotor, inverted: bool, minval: float, maxval: float, smooth: float):
        self.gamepad_axis = gamepad_axis
        self.motor = motor
        self.inverted = inverted
        self.minval = clamp(minval, 0.0, 1.0)
        self.maxval = clamp(maxval, 0.0, 1.0)
        self.smooth = clamp(smooth, 0, MAX_SMOOTHNESS)

        self.input_history = collections.deque([0.0 for _ in range(self.smooth + 1)])

    def process_input(self, value: float, boost: float):
        value = clamp(value, -1.0, 1.0)

        # apply deadzone to thumbsticks
        if 'thumb' in self.gamepad_axis:
            if abs(value) < DEADZONE:
                value = 0.0
            else:
                value = value * (abs(value) - DEADZONE) / (1.0 - DEADZONE)

        if self.inverted:
            value = -value

        value *= boost

        # map value into (minval, maxval) range with appropriate sign
        magnitude = linear_interpolation(self.minval, self.maxval, abs(value))
        value = math.copysign(magnitude, value)

        if self.smooth > 0:
            self.input_history.rotate(1)
            self.input_history[0] = value
            value = sum(self.input_history) / len(self.input_history)

        self.motor.add(value)


class ControlWorker(DeviceWorker):
    def __init__(self, req_port: int, pub_port: int, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

        self.lock = None

        self.gamepad = None
        self.rover = None

        self.active = False
        self.motors = []
        self.mappings = []

    def init_device(self):
        from DeviceServerHeadless import DeviceServerWrapper

        self.lock = threading.Lock()
        self.input_queue = queue.Queue()

        self.device_server = DeviceServerWrapper(self.zmq_context)
        self.reconnect_thread = self.start_timer(self._reconnect, RECONNECT_PERIOD_S)
        threading.Thread(target=self._input_loop, daemon=True).start()

        self.settings = Settings('control')
        threading.Thread(target=self._delayed_config).start()

    def _delayed_config(self):
        time.sleep(5.0)
        config = self.settings.get('config')
        print('settings: {}'.format(config))
        self.configure(config)
        self.start_control()

    def destroy_device(self):
        self.reconnect_thread.stop()
        with self.lock:
            if self.rover is not None:
                self.rover.close()
            if self.gamepad is not None:
                self.gamepad.close()
        self.device_server.close()

    def status(self):
        return { 'is_running': self.active }

    def _reconnect(self):
        from DeviceServerHeadless import DeviceType

        with self.lock:
            if self.rover is None:
                rover = self.device_server.find_device([DeviceType.rover, DeviceType.fake_rover])
                if rover is not None:
                    print('[control] connecting to {}'.format(rover.__class__.__name__))
                    self.rover = rover

            if self.gamepad is None:
                gamepad = self.device_server.find_device([DeviceType.xbox_pad])
                if gamepad is not None:
                    print('[control] connecting to {}'.format(gamepad.__class__.__name__))
                    self.gamepad = gamepad
                    self.gamepad.create_listener_thread(self._recv_input)

    def _recv_input(self, state_raw):
        # print('raw state from xbox: {}'.format(state_raw))
        self.input_queue.put(state_raw)

    def _input_loop(self):
        while True:
            try:
                self._process_last_input()
            except:
                traceback.print_exc()

            time.sleep(0.03)

    def _process_last_input(self):
        state_raw = None
        while True:
            try:
                state_raw = self.input_queue.get_nowait()
                # print('state: {}'.format(state_raw))
            except queue.Empty:
                break

        if state_raw is None:
            return

        try:
            if not self.active:
                return

            rover = self.rover
            if rover is None:
                return

            # print(state_raw)

            try:
                boost = (1 - state_raw['left_trigger']) * (1 + state_raw['right_trigger'])
            except KeyError:
                boost = 1.0

            state = {}
            try:
                alt = (state_raw['button9'] > 0)
            except KeyError:
                alt = False

            for axis in state_raw:
                if alt:
                    state['alt_' + axis] = state_raw[axis]
                    state[axis] = 0.0
                else:
                    state['alt_' + axis] = 0.0
                    state[axis] = state_raw[axis]

            with self.lock:
                for mapping in self.mappings:
                    try:
                        value = float(state.get(mapping.gamepad_axis))
                    except KeyError:
                        continue

                    mapping.process_input(value=value, boost=boost)

                for motor in self.motors:
                    motor.execute()

        except:
            print('[control] error in the input loop')
            traceback.print_exc()

    @remote
    def configure(self, config):
        self.settings.set('config', config)

        with self.lock:
            rover = self.rover
            if rover is None:
                print('[control] cannot configure, no connection to the rover')
                return

            try:
                m_nop = lambda: None
                m_power = getattr(rover, 'power')
                m_servo = getattr(rover, 'servo')
                m_drive = getattr(rover, 'drive')
            except Exception as e:
                print('[control] configure(): {}'.format(e))
                return

        def get_method(cmd: MoveCommand):
            return {
                MoveCommand.NOP: m_nop,
                MoveCommand.POWER: m_power,
                MoveCommand.SERVO: m_servo,
                MoveCommand.DRIVE: m_drive,
            }[cmd]

        try:
            new_motors = []
            new_mappings = []

            for item in config['motors']:
                new_motors.append(VirtualMotor(
                    method=get_method(MoveCommand(item['method'])),
                    axis=item['axis']
                ))

            for item in config['mappings']:
                new_mappings.append(ButtonMapping(
                    gamepad_axis=item['gamepad_axis'],
                    motor=new_motors[item['motor_id']],
                    inverted=item['inverted'],
                    minval=item['minval'],
                    maxval=item['maxval'],
                    smooth=item['smooth']
                ))
        except (KeyError, IndexError) as e:
            print('[control] invalid config: {}'.format(e))

        with self.lock:
            self.motors = new_motors
            self.mappings = new_mappings

    @remote
    def start_control(self):
        self.active = True

    @remote
    def stop_control(self):
        self.active = False


@include_remote_methods(ControlWorker)
class Control(DeviceInterface):
    def __Init__(self, req_port: int, pub_port: int, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port)

    def createDock(self, parentWidget, menu=None):
        pass
