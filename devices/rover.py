
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets,QtCore,QtGui
from time import perf_counter as clock
from time import sleep, time
from collections import deque
from devices.pid import PID
#from devices.temphum import DHT22
from devices.ik import axes_to_arm, axes_to_rover, arm_to_axes, arm_to_rover, rover_to_arm, rover_to_axes
from devices.autonomy import Autonomy, Command, Task, AutoInput
from enum import IntEnum
from scipy import optimize
import subprocess
import math
import random
import socket
import sys
import struct
from math import sin, cos
import threading
from devices.arm_widget import ArmWidget
try:
    import serial
except Exception:
    pass

from devices.reach_tcp import Reach

try:
    import can
except Exception as e:
    print(e)

try:
    import Adafruit_DHT
except Exception:
    pass

try:
    from devices.markers_reader import TagReader
except Exception:
    pass
PI = 3.14159265357
deg = PI / 180
default_req_port = 10200
default_pub_port = 10201

erpm_per_meter = 600 / 1.568 # 96/R_wheel
L1 = 602.
L2 = 478.
deg = PI / 180

arm_lower = 188
arm_upper = 190
arm_rot = 196
grip_lat = 195

pid_settings = {arm_lower: [5, 0, 0.005], arm_upper: [-5, 0, -0.005], arm_rot: [-0.5, 0, -5], grip_lat: [1, 0, 1]}
relative_position_default_origin = (51.470876, -112.752628)#(52.211415, 20.983336)

def list_to_int(bytes):
    return int.from_bytes(bytearray(bytes), byteorder='big', signed=True)

lipo_characteristics = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,6,6,6,6,6,6,6,6,6,7,7,7,7,8,8,8,8,8,9,9,9,10,10,10,11,11,12,12,12,13,13,13,14,14,14,15,16,16,17,17,18,19,19,20,20,21,22,22,24,25,26,27,28,29,31,33,34,36,37,39,41,43,45,46,47,49,50,52,53,54,55,56,56,57,58,59,59,60,62,63,64,64,65,66,66,67,68,68,69,69,70,71,71,72,72,73,73,74,74,75,75,76,77,77,78,78,79,79,80,80,81,81,82,82,83,83,84,84,85,85,86,86,87,87,87,88,88,89,89,90,90,90,91,91,92,92,92,93,93,94,94,94,95,95,95,96,96,96,97,97,97,97,98,98,98,99,99,99,99,99,99,99,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100]


COMMAND_STREAM_PORT = 17293
COMMAND_ID_HISTORY = 100


class MoveCommand(IntEnum):
    NOP = 0
    POWER = 1
    SERVO = 2
    DRIVE = 3


class RoverWorker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.messages = []
        self.wheels = [0, 0, 0, 0]
        self.wheels_target = [0, 0, 0, 0]
        self.wheels_pid = False
        self.wheels_manual = False
        self.wheels_last_time_manual = clock()
        self.wheels_pid_controllers = [PID() for k in range(4)]
        self.battery_v = [0, 0, 0, 0]
        self.compass_pitch = 0.0
        self.compass_roll = 0.0
        self.compass_heading = 0.0
        self.compass_terrain_direction = 0.0
        self.compass_terrain_slope = 0.0
        self.throttle = 0.0
        self.turning = 0.0
        self.position = (24.3, 4.3)
        self.is_ik = False
        self.ikpositions = [0.85 * PI, 0.65 *PI, PI, PI]
        self.encoders = {arm_lower:0, arm_upper:0, arm_rot:0, grip_lat:0}
        self.index_pulses = {arm_lower:500.0, arm_upper:500.0, arm_rot:500.0, grip_lat:500.0}
        self.ik_position = [150 * deg, 90 * deg, 240 * deg, 180 * deg]
        self.ik_speed = [0, 0, 0, 0]
        self.ik_update_timestamp = clock()
        self.ik_watchdog_timestamp = clock() - 1
        self.air_humidity = 0
        self.air_temperature = 0
        self.air_co2 = 0
        self.soil_temperature = 0
        self.soil_humidity = 0
        self.logfile = open("vlog.txt", "a");
        self.logc = 0
        self.script_library = {}
        self.script_is_running = False
        self.autonomy = Autonomy()
        self.available_devices = {}
        self.rover_reversed = False
        self.cmd_socket = None
        self.last_packet_id = None
        self.packet_history = deque()

    def init_device(self):
        self._bus = can.interface.Bus(bustype="socketcan", channel="can0", bitrate=250000)

        self.data_lock = threading.Lock()
        self.msg_lock = threading.Lock()
        self.position_lock = threading.Lock()
        self.auto_lock = threading.Lock()
        self.ik_lock = threading.Lock()

        self.msg_thread = threading.Thread(target=self.loop_read)
        self.msg_thread.start()

        self.wheels_lock = threading.Lock()
        self.position_thread = threading.Thread(target=self.loop_position)
        self.position_thread.start()

        self.ik_thread = threading.Thread(target=self.loop_ik)
        self.ik_thread.start()

        #self.serial_dht22 = serial.Serial('/dev/ttyAMA0', 115200, timeout=5)
        #self.lock_dht22 = threading.Lock()
        #self.thread_dht22 = threading.Thread(target=self.loop_dht22)
        #self.thread_dht22.start()

        self.set_blink()
        self.blink_thread = threading.Thread(target=self.loop_blink)
        self.blink_thread.start()

        try:
            self.reach = Reach()
        except:
            self.reach = None
            print("No connection with reach.")
        self.auto_thread = threading.Thread(target=self.loop_auto)
        self.auto_thread.start()

        self.script_lock = threading.Lock()
        self.script_stop = 0
        self.script_code = ""
        self.script_thread = threading.Thread(target=self.loop_script)
        self.script_thread.start()

        self.send(128, [20,10])
        self.send(400, [100, 0, 100])

        self.servopos = [1500 for i in range(124)]
        self.servopos[0] = 1730
        self.servo(0, 1)

        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_stream_port = COMMAND_STREAM_PORT
        sock_addr = (self.address, self.cmd_stream_port)
        self.cmd_socket.bind(sock_addr)
        self.cmd_stream_loop = threading.Thread(target=self.loop_cmd_stream)
        self.cmd_stream_loop.start()

        #self.tag_reader = TagReader()

        self.send(arm_lower, [18, 100])
        self.send(arm_upper, [18, 100])
        self.send(grip_lat, [18, 100])
        self.send(arm_rot, [18, 100])

        for id, pid in pid_settings.items():
            self.send(id, [35] + list(reversed(bytearray(struct.pack("i", int(10000 * pid[0]))))))
            self.send(id, [36] + list(reversed(bytearray(struct.pack("i", int(10000 * pid[1]))))))
            self.send(id, [37] + list(reversed(bytearray(struct.pack("i", int(10000 * pid[2]))))))

        print("Rover initialized")


    def status(self):
        """ This function will be called periodically to monitor the state 
        of the device. It should return a dictionary describing the current
        state of the device. This dictionary will be delivered to the 
        front-end class."""
        if self.is_ik:
            self.ik(self.ik_x, self.ik_y, self.ik_a, self.ik_d)


        d = super().status()
        d["connected"] = True
        d["position"] = self.get_position()
        d["coordinates"] = self.get_coordinates()
        with self.data_lock:
            d["heading"] = self.compass_heading
            d["terrain_direction"] = self.compass_terrain_direction
            d["terrain_slope"] = self.compass_terrain_slope
            d["voltage"] = sum(self.battery_v) / 40.0
            d["encoders"] = self.encoders
            d["index_pulses"] = self.index_pulses
            d["wheels"] = self.wheels
            d["air_temperature"] = 0 #self.get_air_temperature()
            d["air_humidity"] = 0 #self.get_air_humidity()
            d["air_co2"] = self.air_co2
            d["soil_temperature"] = self.soil_temperature
            d["soil_humidity"] = self.soil_humidity

            s = sum(self.battery_v) - 4 * 2 # 0.2V fix
            if s < 4 * 180:
                i = 0
            elif s >= 4 * 252:
                i = 4 * 72 - 1
            else:
                i = s - 180 * 4

            d['battery'] = lipo_characteristics[i]

        d['autonomy'] = self.autonomy.get_status()

        d['cmd_stream_quality'] = len(self.packet_history) / COMMAND_ID_HISTORY

        self.logfile.write("%f\t%f\n" % (time(), sum(self.battery_v) / 40.0))
        self.logc += 1
        if self.logc % 100 == 0:
            self.logfile.flush()

        return d


    @remote
    def read(self):
        with self.msg_lock:
            for msg in self.messages:
                print((msg.arbitration_id - 1024, list(msg.data)))
            self.messages = []

    def loop_ik(self): # function for constant speed pad arm movement with use of ik
        while True:
            with self.data_lock:
                speed = self.ik_speed
            if speed != [0, 0, 0, 0]:
                self.ik_watchdog_timestamp = clock()
            if self.ik_watchdog_timestamp + 0.5 < clock():
                self.ik_update_timestamp = clock()
                with self.data_lock:
                    self.ik_position = (self.encoders[arm_lower] * deg, self.encoders[arm_upper] * deg, self.encoders[grip_lat] * deg, self.encoders[arm_rot] * deg)
            else:
                #print("ok" + str(speed))
                position = self.ik_position
                position_arm = axes_to_arm(position)
                dt = clock() - self.ik_update_timestamp
                self.ik_update_timestamp = clock()
                position_arm_new = [position_arm[i] + speed[i] * dt for i in range(4)]
                try:
                    position_new = arm_to_axes(position_arm_new)
                    self.ik_position = position_new
                    self.ik(position_new[0:3])
                except Exception as e:
                    print(e)
            sleep(0.030)

    def loop_read(self):
        for msg in self._bus:
            if msg.arbitration_id > 1024:
                with self.data_lock:
                    self.available_devices[msg.arbitration_id - 1024] = True
            if msg.arbitration_id < 1024:
                continue
            elif msg.arbitration_id >= 1024 + 140 and msg.arbitration_id <= 1024 + 143 and msg.data[0] == 30: # wheels encoder
                motor = msg.arbitration_id - 1024 - 140
                with self.msg_lock:
                    self.messages.append(msg)
                with self.data_lock:
                    self.wheels[motor] = int.from_bytes(msg.data[1:5], byteorder='big', signed=True)
                    self.battery_v[motor] = int.from_bytes(msg.data[5:7], byteorder='big', signed=True)
            elif msg.data[0] == 28: # readings from arm encoders
                motor = msg.arbitration_id - 1024
                with self.data_lock:
                    try:
                        self.index_pulses[motor] = (msg.data[3] * 256 + msg.data[4]) / 10
                    except Exception as e:
                        pass
                    self.encoders[motor] = (msg.data[1] * 256 + msg.data[2]) / 10
            elif msg.data[0] == 106:
                reversed_offset = 0
                if self.rover_reversed:
                    reversed_offset = PI
                self.compass_heading = (list_to_int(msg.data[5:7]) * 3.14159 / 180 / 10 + reversed_offset) % (2 * PI)
                self.compass_pitch = list_to_int(msg.data[1:3])  * 3.14159 / 180 / 10
                self.compass_roll = list_to_int(msg.data[3:5])  * 3.14159 / 180 / 10
                self.compass_terrain_direction = (self.compass_heading - math.atan2(self.compass_roll, self.compass_pitch) + reversed_offset) % (2 * PI)
                self.compass_terrain_slope = math.asin((math.sin(self.compass_pitch) ** 2 + math.cos(self.compass_pitch) ** 2 * math.sin(self.compass_roll) ** 2) ** 0.5)
            elif msg.data[0] == 80:
                self.soil_humidity = (2.56 - list_to_int(msg.data[1:3]) * 528 / 624 / 1000) / (2.56 - 1.35) * 100
                print(self.soil_humidity)
            elif msg.data[0] == 83:
                self.air_co2 =((list_to_int(msg.data[1:3]) * 528 / 624 / 1000) - 0.4) / 1.6 * 5000 #* 100 / 13.7
            else:
                with self.msg_lock:
                    self.messages.append(msg)

    @remote
    def set_pid_wheels(self, on=True, params = None):
        self.wheels_target = [v for v in self.wheels]
        if params is not None:
            for i in range(4):
                self.wheels_pid_controllers[i].set_params(params)
        self.wheels_pid = on


    def loop_position(self):
        sleep(1)
        self.last_tacho = self.tacho()
        FPS = 100
        dt = 1.0 / FPS
        last_clock = clock()
        while True:
            with self.data_lock:
                pid = self.wheels_pid
                position = self.wheels
                target = self.wheels_target
            with self.wheels_lock:
                pid = pid and clock() > self.wheels_last_time_manual + 0.5
            if pid:
                for i in range(4):
                    error = target[i] - position[i]
                    power = self.wheels_pid_controllers[i].step(dt, error)
                    self.power(140 + i, power)
            else:
                with self.data_lock:
                    self.wheels_target = [v for v in position]

            tacho = self.tacho()
            dx = tacho - self.last_tacho
            self.last_tacho = tacho
            with self.data_lock:
                heading = self.compass_heading
                self.position = (self.position[0] + math.sin(heading) * dx, self.position[1] + math.cos(heading) * dx)

            while clock() < last_clock + dt:
                pass
            last_clock = clock() + dt

    def loop_dht22(self):
        while 1:
            try:
                sleep(0.1)
                line = self.serial_dht22.readline()
                if line[0:10] == b'Sample OK:':
                    temp = float(line[10:17])
                    hum = float(line[20:27])
                #=================================
                #Sample DHT22...
                #Sample OK: 33.10 *C, 36.30 RH%
                #=================================
                    if hum is not None and temp is not None:
                        with self.lock_dht22:
                            self.air_humidity = hum
                            self.air_temperature = temp
            except Exception as e:
                print(e)

    def loop_blink(self):
        while True:
            sleep(0.5)
            if self.blink == 1:
                self.power(210, -1)
            sleep(0.5)
            self.power(210, 0)

    @remote
    def set_blink(self, on = 1):
        self.blink = on

    def loop_auto(self):
        while True:
            try:
                while True:
                    if not self.autonomy.is_running():
                        sleep(0.5)
                        continue

                    auto_input = AutoInput(
                        position=self.get_coordinates(),
                        heading=self.get_orientation(),
                        script_running=self.is_script_running()
                    )

                    with self.auto_lock:
                        cmd_type, args = self.autonomy.get_command(auto_input)

                        print(cmd_type, args)

                        if cmd_type == Command.NOP:
                            self.drive_both_axes(0.0, 0.0)
                        elif cmd_type == Command.SET_THROTTLE_TURNING:
                            throttle, turning = args
                            self.drive_both_axes(throttle, turning)
                        elif cmd_type == Command.RUN_SCRIPT:
                            name, = args[0]
                            self.run_script(self.script_library[name])
                            pass
            except Exception as e:
                print('loop_auto(): {}'.format(str(e)))

    @remote
    def auto_set_tasks(self, tasks):
        try:
            with self.auto_lock:
                self.autonomy.set_tasks(tasks)
        except Exception as e:
            print('set_tasks(): {}'.format(str(e)))

    @remote
    def start_auto_from_task(self, task: int = 0):
        try:
            with self.auto_lock:
                self.autonomy.start(task)
        except Exception as e:
            print('start_auto_from_task(): {}'.format(str(e)))

    @remote
    def end_auto(self):
        print('trying to stop autonomy')
        try:
            with self.auto_lock:
                self.autonomy.halt()
        except Exception as e:
            print('end_auto(): {}'.format(str(e)))

    @remote
    def get_auto_status(self):
        try:
            with self.auto_lock:
                return self.autonomy.get_status()
        except Exception as e:
            print('get_auto_status(): {}'.format(str(e)))
            return '<exception occured>'

    @remote
    def get_coordinates(self):
        if self.reach is not None:
            return self.reach.get_status()
        else:
            return (0, 0)

    @remote
    def get_orientation(self):
        with self.data_lock:
            o = self.compass_heading
        return o

    @remote
    def get_position(self, origin=relative_position_default_origin, axis=-1):
        coords = self.get_coordinates()
        x = (coords[1] - origin[1]) * deg * 6371000 * math.cos(coords[0] * deg)
        y = (coords[0] - origin[0]) * deg * 6371000
        if axis == 0:
            return x
        elif axis == 1:
            return y
        else:
            return (x, y)

    @remote
    def abort_script(self):
        with self.script_lock:
            self.script_stop = 1
            self.script_code = ""

    @remote
    def run_script(self, code):
        with self.script_lock:
            self.script_stop = 0
            self.script_code = code

    @remote
    def is_script_running(self):
        return self.script_is_running

    def loop_script(self):
        while True:
            def is_number(s):
                try:
                    float(s)
                    return True
                except ValueError:
                    return False

            self.script_is_running = False
            while True:
                sleep(0.1)
                with self.script_lock:
                    code = self.script_code
                    self.script_code = ""
                if code != "":
                    break
            self.script_is_running = True
            lines = [line.split() for line in code.split("\n")]
            print(lines)
            var_dict = {}
            functions = {}
            code_time = 0
            abort = False
            start = clock()
            for line in lines:
                if line == []:
                    continue
                line_err = str(line)
                try:
                    first = line.pop(0)
                    if is_number(first):
                        code_time += float(first)
                        while line != []:
                            command = line.pop(0)
                            if command == "x":
                                args = (float(line.pop(0)) * deg, float(line.pop(0)) * deg, float(line.pop(0)) * deg, float(line.pop(0)) * deg)
                                functions["__ik__"] = lambda args=args : self.ik(args)
                            elif command == "a":
                                args = (float(line.pop(0)), float(line.pop(0)), float(line.pop(0)) * deg, float(line.pop(0)) * deg)
                                functions["__ik__"] = lambda args=args: self.ik(arm_to_axes(args))
                            elif command == "r":
                                args = (float(line.pop(0)), float(line.pop(0)), float(line.pop(0)), float(line.pop(0)) * deg)
                                functions["__ik__"] = lambda args=args: self.ik(rover_to_axes(args))
                            elif command == "apply_index":
                                self.apply_index()
                            else:
                                if is_number(command):
                                    motor = int(command)
                                else:
                                    motor = var_dict[command]
                                power = float(line.pop(0))
                                if abs(power) < 0.000001:
                                    self.power(motor, 0)
                                    functions[motor] = lambda: None
                                else:
                                    functions[motor] = lambda motor=motor, power=power: self.power(motor, power)

                    else:
                        var_dict[first] = int(line.pop(0))

                    while clock() < start + code_time:  # sync with code_time
                        for key in functions:
                            functions[key]()
                        towait = max(0, min(0.1, start + code_time - clock()))
                        sleep(towait)
                        with self.script_lock:
                            if self.script_stop == 1:
                                self.script_stop = 0
                                abort = True
                        if abort:
                            print("abort")
                            break
                except Exception as e:
                    print(str(e) + " while processing line " + line_err)
                    break
                if abort:
                    break
            abort = True

    def loop_cmd_stream(self):
        while True:
            try:
                data, addr = self.cmd_socket.recvfrom(4096)
                packet_id = struct.unpack('I', data[:4])[0]

                def preceed(first, second):
                    return ((first + 2**32 - second) % (2**32) > (2**31))

                if self.last_packet_id is None:
                    self.last_packet_id = packet_id
                    self.packet_history.append(packet_id)
                else:
                    if not preceed(self.last_packet_id, packet_id):
                        # old packet, drop
                        continue
                    else:
                        self.last_packet_id = packet_id
                        self.packet_history.append(packet_id)
                        while (packet_id + 2**32 - self.packet_history[0]) % (2**32) >= COMMAND_ID_HISTORY:
                            self.packet_history.popleft()

                for cmd, axis, power in struct.iter_unpack('Bhf', data[4:]):
                    cmd = MoveCommand(cmd)
              
                    # print('[rover] execute {}({}, {})'.format(cmd, axis, power))

                    if cmd == MoveCommand.POWER:
                        self.power(axis, power)
                    elif cmd == MoveCommand.SERVO:
                        self.servo(self, axis, power)
                    elif cmd == MoveCommand.DRIVE:
                        self.drive(axis, power)
            except Exception as e:
                print('[rover] loop_cmd_stream(): {}'.format(e))

    @remote
    def get_cmd_stream_port(self):
        return self.cmd_stream_port

    @remote
    def fix_pos(self, x, y):
        self.position = (x, y)

    @remote
    def servo(self, id, move):
        self.servopos[id] += move
        if self.servopos[id] > 2500:
            self.servopos[id] = 2500
        if self.servopos[id] < 500:
            self.servopos[id] = 500
        if id // 8 == 0:
            self.send(306, [5, id % 8, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
        if id // 8 == 1:
            self.send(305, [5, id % 8, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
        if id // 8 == 2:
            self.send(307, [5, id % 8, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
        if id == 101:
            self.send(305, [5, 0, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
            self.send(305, [5, 1, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
            self.send(305, [5, 2, int(3000-self.servopos[id]) >> 8, int(3000-self.servopos[id]) & 0xff])
            self.send(305, [5, 3, int(3000-self.servopos[id]) >> 8, int(3000-self.servopos[id]) & 0xff])
        if id == 100:
            self.send(305, [5, 4, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
            self.send(305, [5, 5, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])



    @remote
    def servo_pos(self, id, pos):
        if id // 8 == 0:
            self.send(306, [5, id % 8, int(pos) >> 8, int(pos) & 0xff])
        if id // 8 == 1:
            self.send(305, [5, id % 8, int(pos) >> 8, int(pos) & 0xff])
        if id // 8 == 2:
            self.send(307, [5, id % 8, int(pos) >> 8, int(pos) & 0xff])
        if id == 101:
            self.send(305, [5, 0, int(pos) >> 8, int(pos) & 0xff])
            self.send(305, [5, 1, int(pos) >> 8, int(pos) & 0xff])
            self.send(305, [5, 2, int(3000 - pos) >> 8, int(3000 - pos) & 0xff])
            self.send(305, [5, 3, int(3000 - pos) >> 8, int(3000 - pos) & 0xff])
        if id == 100:
            self.send(305, [5, 4, int(pos) >> 8, int(pos) & 0xff])
            self.send(305, [5, 5, int(pos) >> 8, int(pos) & 0xff])

    @remote
    def servos(self):
        return [("servo_306:" + str(i%8), i) for i in range(0, 8)] + \
               [("servo_305:" + str(i%8), i) for i in range(8, 16)] + \
               [("servo_307:" + str(i%8), i) for i in range(16, 24)] + \
               [("arm_upper: 100", 100), ("grip_clamp: 101", 101)]

    @remote
    def tags(self):
        list = [None for i in range(35)]
        markers = []# self.tag_reader.get_markers()
        for i, data in markers:
            print(i, data)
            d0 = float(data[0])
            d2 = float(data[2])
            with self.data_lock:
                a = (math.atan2(d0, d2) + self.compass_heading) % (2 * PI)
            r = (d0 ** 2 + d2 ** 2) ** 0.5
            print(a, r, i)
            list[int(i)] = (a, r)
        return list

    @remote
    def slope_points(self):
        with self.data_lock:
            slope = self.compass_terrain_slope
            direction = self.compass_terrain_direction
        if slope > 12 / 180 * PI:
            return([(t[0], t[1]) for t in slopepoints if abs((t[2] - direction + PI) % (2 * PI) - PI) < PI / 6])
        else:
            return []

    @remote
    def tacho(self):
        with self.data_lock:
            return 0.5 * (self.wheels[1] - self.wheels[3]) / erpm_per_meter

    @remote
    def send(self, id, data):
        self._bus.send(can.Message(arbitration_id=id, data = data, extended_id = False))

    @remote
    def start_ik(self):
        alfa = 796 + 900
        beta = 1253
        self.send(arm_lower, [38, alfa >> 8, alfa & 0xff])
        self.send(arm_upper, [38, beta >> 8, beta & 0xff])
        self.send(grip_lat, [38, 1800 >> 8, 1800 & 0xff])
        self.send(arm_rot, [38, 1800 >> 8, 1800 & 0xff])

    @remote
    def apply_index(self):
        def set(motor, angle):
            a = int(angle * 10)
            if a < 0:
                a = 0
            if a >= 3600:
                a = 3599
            self.send(motor, [38, a >> 8, a & 0xff])
        set(arm_lower, self.encoders[arm_lower] + 153.8 + 7.3 - self.index_pulses[arm_lower])
        set(arm_upper, self.encoders[arm_upper] + 117.7 - 2.4 - self.index_pulses[arm_upper])
        set(grip_lat, self.encoders[grip_lat] + 152.0 - 3.2 - self.index_pulses[grip_lat])
        set(arm_rot, self.encoders[arm_rot] + 300 - self.index_pulses[arm_rot])

    @remote
    def get_encoders(self):
        return self.encoders

    @remote
    def get_index_pulses(self):
        return self.index_pulses

    @remote
    def set_ik(self, on = True):
        self.is_ik = on

    @remote
    def ik_deg(self, tx, ty, ta, td):
        self.ik(tx, ty, ta * PI / 180, td * PI / 180)

    @remote
    def ik(self, params): # execute given goal angles - send to motor drivers
        if len(params) == 4:
            outa, outb, outc, outd = [int((v % (2 * PI)) * 1800 / PI) for v in params]
            self._bus.send(can.Message(arbitration_id=int(arm_lower),
                                         data=[8, (outa >> 8) & 0xff, outa & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(arm_upper),
                                         data=[8, (outb >> 8) & 0xff, outb & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(grip_lat),
                                         data=[8, (outc >> 8) & 0xff, outc & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(arm_rot),
                                         data=[8, (outd >> 8) & 0xff, outd & 0xff], extended_id=False))
        else: # without arm rotation
            outa, outb, outc = [int((v % (2 * PI)) * 1800 / PI) for v in params]
            self._bus.send(can.Message(arbitration_id=int(arm_lower),
                                         data=[8, (outa >> 8) & 0xff, outa & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(arm_upper),
                                         data=[8, (outb >> 8) & 0xff, outb & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(grip_lat),
                                         data=[8, (outc >> 8) & 0xff, outc & 0xff], extended_id=False))
    @remote
    def ik_arm(self, params):
        print(params)
        print(arm_to_axes(params))
        self.ik(arm_to_axes(params))

    @remote
    def ik_rover(self, params):
        self.ik(rover_to_axes(params))

    @remote
    def power(self, id, power):
        power = float(power)
        if id >= 2000 and id <= 2001:
            self.ik_speed[id - 2000] = power
        elif id >= 2002 and id <= 2003:
            self.ik_speed[id - 2000] = power * deg
        else:
            if power < -1:
                power = - 1
            if power > 1:
                power = 1
            out = round((2 ** 15 - 1) * power)
            if out < 0:
                   out += 2 ** 16
            self._bus.send(can.Message(arbitration_id=int(id), data=[7, out >> 8, out & 0xff], extended_id=False))

    @remote
    def update_script_library(self, library):
        self.script_library = library

    @remote
    def drive(self, axis, power):
        # print("drive")
        if axis == 0:  # throttle
            self.throttle = power
        if axis == 1:  # turning
            self.turning = power

        with self.wheels_lock:
            if abs(self.throttle) + abs(self.turning) > 0.000001:
                self.wheels_last_time_manual = clock()
        left = self.throttle + self.turning
        right = -self.throttle + self.turning

        if not self.rover_reversed:
            self.power(129, left)
            self.power(130, right)
        else:
            self.power(130, left)
            self.power(129, right)


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
               ] \
               + [
                   ("arm_ik_forward", 2000),
                   ("arm_ik_up", 2001),
                   ("arm_ik_grip", 2002),
                   ("arm_ik_left", 2003)
               ] \
               + [("wheel_" + str(i - 140), i) for i in range(140, 144)] \
               + [("", i) for i in range(185, 200)] \
               + [("", i) for i in range(202, 210)]

    @remote
    def get_air_temperature(self):
        with self.lock_dht22:
            return round(self.air_temperature, 2)

    @remote
    def get_air_humidity(self):
        with self.lock_dht22:
            return round(self.air_humidity, 2)

    @remote
    def get_available_devices(self):
        with self.data_lock:
            return list(self.available_devices)

    @remote
    def reset_available_devices(self):
        with self.data_lock:
            self.available_devices = {}

    @remote
    def set_rover_reversed(self, reversed = True):
        self.rover_reversed = reversed


    
@include_remote_methods(RoverWorker)
class Rover(DeviceOverZeroMQ):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_status = {}

    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Dummy device", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        widget.setLayout(layout)
        vwidget = QtWidgets.QWidget()
        layout_imu = QtWidgets.QGridLayout(vwidget)
        layout_sensors = QtWidgets.QGridLayout(vwidget)
        layout.addWidget(vwidget)
        layout.addLayout(layout_sensors)
        self.button_send = QtWidgets.QPushButton("SEND", parentWidget)

        self.battery_bar = QtWidgets.QProgressBar()
        self.battery_bar.setOrientation(QtCore.Qt.Vertical)
        self.battery_bar.setRange(0,100)
        self.battery_bar.setTextVisible(True)
        self.battery_label = QtWidgets.QLabel()
        self.battery_label.setFixedWidth(45)
        layout.addWidget(self.battery_label)
        layout.addWidget(self.battery_bar)
        self.edits = []
        self.edits_sensors = []
        self.edits_encoder_position = []
        self.edits_index_pulses_positions = []
        self.editswheels = []
        self.labels_encoders = []
        for i in range(3):
            edit = QtWidgets.QLineEdit()
            edit.setFixedWidth(100)
            layout_imu.addWidget(QtWidgets.QLabel(["Azimuth", "Terrain azimuth", "Terrain slope"][i]), i, 0)
            layout_imu.addWidget(edit, i, 1)
            self.edits.append(edit)

        for i in range(5):
            edit = QtWidgets.QLineEdit()
            edit.setFixedWidth(100)
            layout_sensors.addWidget(QtWidgets.QLabel(["Air temp.", "Air hum.", "Air co2 (ppm)", "Soil temp.", "Soil hum."][i]), i, 0)
            layout_sensors.addWidget(edit, i, 1)
            self.edits_sensors.append(edit)

        ewidget = QtWidgets.QWidget()
        elayout = QtWidgets.QGridLayout(ewidget)
        layout.addWidget(ewidget)

        for i in range(4):
            editwheel = QtWidgets.QLineEdit()
            editwheel.setFixedWidth(45)
            elayout.addWidget(editwheel, i, 0)
            self.editswheels.append(editwheel)
            labelenc = QtWidgets.QLabel("None")
            elayout.addWidget(labelenc, i, 1)
            self.labels_encoders.append(labelenc)
            editenc = QtWidgets.QLineEdit()
            editenc.setFixedWidth(45)
            elayout.addWidget(editenc, i, 2)
            self.edits_encoder_position.append(editenc)
            editind = QtWidgets.QLineEdit()
            editind.setFixedWidth(45)
            elayout.addWidget(editind, i, 3)
            self.edits_index_pulses_positions.append(editind)

        pidwidget = QtWidgets.QWidget()
        pidlayout = QtWidgets.QVBoxLayout(pidwidget)
        layout.addWidget(pidwidget)

        self.button_pid = QtWidgets.QPushButton("Lock Wheels")
        pidlayout.addWidget(self.button_pid)
        self.button_pid.clicked.connect(self.lock_pid)
        self.button_pid.setCheckable(True)
        self.pid_locked = False

        layout_position = QtWidgets.QVBoxLayout()
        self.edit_position_x = QtWidgets.QLineEdit()
        self.edit_position_x.setFixedWidth(90)
        self.edit_position_y= QtWidgets.QLineEdit()
        self.edit_position_y.setFixedWidth(90)
        self.edit_position_lon= QtWidgets.QLineEdit()
        self.edit_position_lon.setFixedWidth(90)
        self.edit_position_lat= QtWidgets.QLineEdit()
        self.edit_position_lat.setFixedWidth(90)
        layout_position.addWidget(self.edit_position_x)
        layout_position.addWidget(self.edit_position_y)
        layout_position.addWidget(self.edit_position_lon)
        layout_position.addWidget(self.edit_position_lat)
        layout_position.addStretch(1)
        layout.addLayout(layout_position)
        self.arm_widget = ArmWidget(dock)
        layout.addWidget(self.arm_widget)

        layout_connection = QtWidgets.QFormLayout()
        self.cmd_stream_quality = QtWidgets.QLabel('?')
        layout_connection.addRow(QtWidgets.QLabel('Connection quality:'), self.cmd_stream_quality)
        layout.addLayout(layout_connection)

        layout.addStretch(1)

        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
            
        # Following lines "turn on" the widget operation
        #self.increaseVoltageButton.clicked.connect(lambda pressed: self.incVoltage())
        self.createListenerThread(self.updateSlot)

    def lock_pid(self):
        if self.pid_locked:
            self.pid_locked = False
            self.button_pid.setDown(False)
            self.set_pid_wheels(0)
        else:
            self.pid_locked = True
            self.button_pid.setDown(True)
            self.set_pid_wheels(1)

        
    def updateSlot(self, status):
        self.last_status = status

        self.edits_sensors[0].setText(str(round(status["air_temperature"], 2)))
        self.edits_sensors[1].setText(str(round(status["air_humidity"], 2)))
        self.edits_sensors[2].setText(str(round(status["air_co2"], 2)))
        self.edits_sensors[3].setText(str(round(status["soil_temperature"], 2)))
        self.edits_sensors[4].setText(str(round(status["soil_humidity"], 2)))
        self.edits[0].setText(str(round(status["heading"] / deg, 2)))
        self.edits[1].setText(str(round(status["terrain_direction"] / deg, 2)))
        self.edits[2].setText(str(round(status["terrain_slope"] / deg, 2)))
        self.battery_bar.setValue(status["battery"])
        self.battery_label.setText(str(status["battery"]) + '%\n' + str(round(status["voltage"], 2)) + ' V\n' + str(round(status["voltage"] / 6, 2)) + ' V\n')
        self.edit_position_x.setText(str(round(status["position"][0], 2)))
        self.edit_position_y.setText(str(round(status["position"][1], 2)))
        self.edit_position_lon.setText(str(round(status["coordinates"][0], 6)))
        self.edit_position_lat.setText(str(round(status["coordinates"][1], 6)))
        self.cmd_stream_quality.setText(str(status['cmd_stream_quality']))

        for i in range(4):
            self.editswheels[i].setText(str(status["wheels"][i]))
        motors = list(status["encoders"].keys())
        motors.sort()
        for i in range(4):
            self.labels_encoders[i].setText("arm axis " + str(motors[i]))
            self.edits_encoder_position[i].setText(str(status["encoders"][motors[i]]))
            self.edits_index_pulses_positions[i].setText(str(status["index_pulses"][motors[i]]))
        #print(status["encoders"])
        #print(status["encoders"][str(arm_lower)])
        #print(status["encoders"][str(arm_upper)])
        #print(status["encoders"][str(grip_lat)])
        try:
            self.arm_widget.set_angles([status["encoders"][str(arm_lower)] * deg, status["encoders"][str(arm_upper)] * deg, status["encoders"][str(grip_lat)] * deg])
        except Exception as e:
            print(str(e))

    def send_from_gui(self):
        print(self.edits[0].text())
        print(self.edits[1].text())
        self.power(self.edits[0].text(), self.edits[1].text())
		
    def get_last_status(self):
        return self.last_status


    def set_waypoints(self, waypoints):
        tasks = [(Command.DRIVE_TO, (waypoint,)) for waypoint in waypoints]  
        self.auto_set_tasks(tasks)

    def set_tasks(self, tasks):
        self.auto_set_tasks(tasks)


    #def get_position(self, axis):
    #    #with self.data_lock:
    #    return axis
