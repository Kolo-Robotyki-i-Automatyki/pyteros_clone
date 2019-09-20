from collections import namedtuple
from enum import IntEnum
import sys
import time

from devices.zeromq_device import DeviceWorker, DeviceInterface, remote, include_remote_methods
from src.common.coord import *
from src.common.misc import *


MIN_DESTINATION_DIST = 0.5
MIN_SCRIPT_WAIT_TIME = 10.0

DEVICE_DISCOVERY_PERIOD = 3.0
MAIN_LOOP_PERIOD = 0.1

MAX_FAILED_CONNNECTIONS = 3


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

class CmdType(IntEnum):
    NOP = 1
    SET_THROTTLE_TURNING = 2
    RUN_SCRIPT = 3

Command = namedtuple('Command', ['type', 'args'])


class AutoInput:
    def __init__(self, position, heading: float, script_running: bool):
        self.position = position
        self.heading = heading
        self.script_running = script_running


class AutonomyCore:
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
            command = func(auto_input)
        except Exception as e:
            self.debug_status['exception'] = str(e)
            command = Command(CmdType.NOP, ())

        self.debug_status['last_command'] = str(command)

        return command

    def _auto_idle(self, auto_input):
        return Command(CmdType.NOP, ())

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
        return Command(CmdType.NOP, ())

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
            return Command(CmdType.NOP, ())

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
        return Command(CmdType.SET_THROTTLE_TURNING, (throttle, turning))

    def _auto_launch_script(self, auto_input):
        script_name, = self.params
        
        self.state = State.WAIT_FOR_SCRIPT_COMPLETION
        self.params = time.time()

        return Command(CmdType.RUN_SCRIPT, (script_name,))

    def _auto_wait_for_script_completion(self, auto_input):
        start_time = self.params
        now = time.time()

        if now - start_time < MIN_SCRIPT_WAIT_TIME:
            self.debug_status['time_waiting'] = now - start_time
        else:
            if not auto_input.script_running:
                self.state = State.GET_NEXT_TASK
                self.params = None
            
        return Command(CmdType.NOP, ())


class AutonomyWorker(DeviceWorker):
    def __init__(self, req_port, pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

        self.rover = None
        self.core = None
        self.reconnect_thread = None
        self.run_thread = None

        self.failed_connections = 0

    def init_device(self):
        from DeviceServerHeadless import DeviceServer

        self.device_server = DeviceServer(self.zmq_context)
        self.core = AutonomyCore()
        self.reconnect_thread = self.start_periodic_task(self._find_rovers, self._reconnect, DEVICE_DISCOVERY_PERIOD)
        self.run_thread = self.start_timer(self._auto_step, MAIN_LOOP_PERIOD)

    def destroy_device(self):
        self.run_thread.stop()
        self.reconnect_thread.stop()
        self.device_server.close()
        if self.rover is not None:
            self.rover.close()

    def status(self):
        status = self.core.get_status()
        status.update(rover_type=self.rover.__class__.__name__)
        return status

    def _find_rovers(self):
        from DeviceServerHeadless import DeviceType, DeviceServer

        try:
            devices = self.device_server.devices()
        except ConnectionError:
            print('no connection to the device server', file=sys.stderr)
            return
        except:
            traceback.print_exc()
            return

        real = None
        fake = None

        for dev in devices:
            if dev.dev_type == DeviceType.rover:
                real = dev
            elif dev.dev_type == DeviceType.fake_rover:
                fake = dev

        if real is not None:
            return (real.dev_type, real.req_port, real.pub_port, real.address)
        elif fake is not None:
            return (fake.dev_type, fake.req_port, fake.pub_port, fake.address)
        else:
            return None

    def _reconnect(self, dev_descr):
        from DeviceServerHeadless import DEVICE_TYPE_INFO

        if self.rover is not None:
            return

        if dev_descr is None:
            return

        dev_type, req_port, pub_port, address = dev_descr
        _, _, interface_class = DEVICE_TYPE_INFO[dev_type]
        self.rover = interface_class(req_port=req_port, pub_port=pub_port, host=address, zmq_context=self.zmq_context)

    def _auto_step(self):
        if not self.core.is_running():
            return

        rover = self.rover
        if rover is None:
            return

        try:
            auto_input = AutoInput(
                position=rover.get_coordinates(),
                heading=rover.get_orientation(),
                script_running=rover.is_script_running()
            )

            cmd = self.core.get_command(auto_input)
            if cmd.type == CmdType.NOP:
                rover.drive_both_axes(0.0, 0.0)
            elif cmd.type == CmdType.SET_THROTTLE_TURNING:
                throttle, turning = cmd.args
                rover.drive_both_axes(throttle, turning)
            elif cmd.type == CmdType.RUN_SCRIPT:
                name = cmd.args[0]
                rover.run_script(rover.script_library[name])
            self.failed_connections = max(self.failed_connections - 1, 0)
        except ConnectionError:
            print('can\'t connect to the rover', file=sys.stderr)
            self.failed_connections += 1
            if self.failed_connections >= MAX_FAILED_CONNNECTIONS:
                self.failed_connections = 0
                self.rover.close()
                self.rover = None

    @remote
    def set_tasks(self, tasks):
        try:
            self.core.set_tasks(tasks)
        except Exception as e:
            print('set_tasks(): {}'.format(str(e)))

    @remote
    def start_from_task(self, task: int = 0):
        try:
            self.core.start(task)
        except Exception as e:
            print('start_from_task(): {}'.format(str(e)))

    @remote
    def end(self):
        try:
            self.core.halt()
        except Exception as e:
            print('end(): {}'.format(str(e)))


@include_remote_methods(AutonomyWorker)
class Autonomy(DeviceInterface):
    def __init__(self, req_port, pub_port, host, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, host=host, **kwargs)

    def createDock(self, parentWidget, menu=None):
        pass
