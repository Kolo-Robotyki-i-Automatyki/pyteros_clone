import collections
import enum
import json
import multiprocessing
import random
import select
import socket
import threading
import time
import traceback
import zmq

from devices.autonomy import AutonomyWorker, Autonomy
from devices.cameras import CameraServerWorker, CameraServer
from devices.control import ControlWorker, Control
from devices.fake_rover import FakeRoverWorker, FakeRover
from devices.misc.xbox import XBoxWorker, XBoxPad
from devices.rover import RoverWorker, Rover
from devices.zeromq_device import remote, include_remote_methods
from devices.zeromq_device import DeviceWorker, DeviceInterface, PublisherTopic
from src.common.misc import NumpyArrayEncoder, NumpyArrayDecoder


SERVER_DISCOVERY_PORT = 51001
SERVER_DISCOVERY_PERIOD_S = 0.2
SERVER_TIMEOUT_S = 2.0

SERVER_REQ_PORT = 51002
SERVER_PUB_PORT = 51003
DEVICE_PORT_RANGE = (51000, 52000)

SERVER_REFRESH_PERIOD_S = 0.5


DeviceType = enum.IntEnum('DeviceType', [
    'rover',
    'fake_rover',
    'autonomy',
    'xbox_pad',
    'camera_server',
    'control',
])

DEVICE_TYPE_INFO = {
    DeviceType.rover: ('Rover', RoverWorker, Rover),    
    DeviceType.fake_rover: ('Fake rover', FakeRoverWorker, FakeRover),
    DeviceType.autonomy: ('Autonomy', AutonomyWorker, Autonomy),
    DeviceType.xbox_pad: ('XBox pad', XBoxWorker, XBoxPad),
    DeviceType.camera_server: ('Camera server', CameraServerWorker, CameraServer),
    DeviceType.control: ('Control', ControlWorker, Control),
}

class HostStruct:
    __slots__ = [
        'address',
        'last_seen',
        'interface',
    ]

    def __init__(self, zmq_context, address, last_seen):
        self.address = address
        self.last_seen = time.time()
        self.interface = DeviceServer(zmq_context=zmq_context, address=address)

class DeviceStruct:
    __slots__ = [
        'dev_type',
        'req_port',
        'pub_port',
        'process',
        'interface',
    ]

    def __init__(self, dev_type, zmq_context, req_port, pub_port, process):
        self.dev_type = dev_type
        self.req_port = req_port
        self.pub_port = pub_port
        self.process = process
        _, _, interface_class = DEVICE_TYPE_INFO[dev_type]
        self.interface = interface_class(zmq_context=zmq_context, req_port=req_port, pub_port=pub_port, host='localhost')


class DeviceWorkerProcess(multiprocessing.Process):
    """Process that runs a DevieWorker"""
    def __init__(self, dev_type, args, kwargs):
        super().__init__()

        self.dev_type = dev_type
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            _, worker_class, _ = DEVICE_TYPE_INFO[self.dev_type]
            device = worker_class(*self.args, **self.kwargs)
            device.run()
        except:
            traceback.print_exc()


class DeviceServerWorker(DeviceWorker):
    """Server that runs other DeviceWorkers in separate processes"""
    def __init__(self):
        super().__init__(req_port=SERVER_REQ_PORT, pub_port=SERVER_PUB_PORT, refresh_period=SERVER_REFRESH_PERIOD_S)

        self.hostname = socket.gethostname()
        self.hosts = {}
        self.local_devices = {}
        self.external_devices = {}
        self.used_ports = set()

    def init_device(self):
        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.discovery_socket.bind(('', SERVER_DISCOVERY_PORT))

        self.start_periodic_task(self._discover_hosts, self._update_hosts, SERVER_DISCOVERY_PERIOD_S)
 
    def destroy_device(self):
        for name, dev_info in self.local_devices.items():
            try:
                dev_info.interface.stop()
            except ConnectionError:
                pass
            dev_info.interface.close()
        for name, host_info in self.hosts.items():
            host_info.interface.close()

    def status(self):
        status = {
            'name': self.hostname,
            'hosts': self.get_hosts(),
            'devices': self.get_devices(),
        }
        return status

    @remote
    def get_hosts(self):
        result = {}
        time_now = time.time()
        for hostname, descr in self.hosts.items():
            result[hostname] = {
                'address': descr.address,
                'connected': (descr.last_seen + SERVER_TIMEOUT_S > time_now),
            }
        return result

    @remote
    def get_local_devices(self):
        result = []
        for name, data in self.local_devices.items():
            dev_descr = {
                'name': name,
                'dev_type': data.dev_type,
                'req_port': data.req_port,
                'pub_port': data.pub_port,
                'address': self.hosts.get(self.hostname).address,
            }
            result.append(dev_descr)
        return result

    @remote
    def get_devices(self):
        all_devices = self.external_devices
        all_devices.update({ self.hostname: self.get_local_devices() })
        return all_devices

    @remote
    def start_device(self, dev_type, host = None, args = (), kwargs = {}):
        if host not in [None, 'localhost', self.hostname]:
            interface = self.hosts[host].interface
            interface.start_device(dev_type, host, args, kwargs)
        else:
            self._start_local_device(DeviceType(dev_type), args, kwargs)

    @remote
    def stop_device(self, name, host = None):
        if host not in [None, 'localhost', self.hostname]:
            interface = self.hosts[host].interface
            interface.stop_device(name, host)
        else:
            self._stop_local_device(name)

    def _start_local_device(self, dev_type, args, kwargs):
        print('starting device of type "{}"'.format(dev_type.name))

        pub_port = self._get_random_port()
        req_port = self._get_random_port()
        name = dev_type.name + str(req_port)
        kwargs.update(dict(req_port=req_port, pub_port=pub_port))
        process = DeviceWorkerProcess(dev_type, args, kwargs)
        process.start()

        dev_data = DeviceStruct(dev_type, self.zmq_context, req_port, pub_port, process)
        self.local_devices[name] = dev_data

    def _stop_local_device(self, name):
        print('stopping device "{}"'.format(name))

        try:
            dev_data = self.local_devices.pop(name)
        except KeyError:
            print('device {} is not running'.format(name))
            return

        dev_data.interface.stop()
        dev_data.interface.close()

        self.used_ports.remove(dev_data.req_port)
        self.used_ports.remove(dev_data.pub_port)

    def _get_random_port(self):
        while True:
            port = random.randrange(*DEVICE_PORT_RANGE)
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port

    def _discover_hosts(self):
        socket = self.discovery_socket

        msg = self.hostname.encode('utf-8')
        socket.sendto(msg, ('<broadcast>', SERVER_DISCOVERY_PORT))

        detected_hosts = {}
        while True:
            ready, _, _ = select.select([socket], [], [], 0.0)
            if len(ready) == 0:
                break

            msg, (address, port) = socket.recvfrom(1024)
            hostname = msg.decode('utf-8')
            detected_hosts[hostname] = address

        return detected_hosts

    def _update_hosts(self, new_hosts):
        time_now = time.time()
        for hostname, address in new_hosts.items():
            if hostname not in self.hosts:
                host_data = HostStruct(self.zmq_context, address, time_now)
                self.hosts[hostname] = host_data
                if hostname != self.hostname:
                    endpoint = 'tcp://{}:{}'.format(address, SERVER_PUB_PORT)
                    self.connect_to_endpoint(endpoint, zmq.SUB, self._update_external_devices)
            else:
                self.hosts[hostname].last_seen = time_now

    def _update_external_devices(self, host_msg):
        topic = host_msg.get('topic')
        if topic != PublisherTopic.status:
            return
        status = host_msg.get('contents')
        hostname = status.get('name')
        devices = status.get('devices').get(hostname)
        self.external_devices[hostname] = devices


@include_remote_methods(DeviceServerWorker)
class DeviceServer(DeviceInterface):
    def __init__(self, zmq_context, address = 'localhost'):
        super().__init__(req_port=SERVER_REQ_PORT, pub_port=SERVER_PUB_PORT, host=address, zmq_context=zmq_context)

    def stop(self):
        raise Exception('DeviceServer should never be stopped')


class HostDescription:
    __slots__ = ['hostname', 'address', 'connected']

    def __init__(self, hostname, address, connected):
        self.hostname = hostname
        self.address = address
        self.connected = connected

class DeviceDescription:
    __slots__ = ['name', 'dev_type', 'req_port', 'pub_port', 'address', 'hostname']

    def __init__(self, name, dev_type, req_port, pub_port, address, hostname):
        self.name = name
        self.dev_type = DeviceType(dev_type)
        self.req_port = req_port
        self.pub_port = pub_port
        self.address = address
        self.hostname = hostname

    def interface(self, zmq_context):
        _, _, interface_class = DEVICE_TYPE_INFO.get(self.dev_type)
        return interface_class(zmq_context=zmq_context, req_port=self.req_port, pub_port=self.pub_port, host=self.address)

class DeviceServerWrapper:
    def __init__(self, zmq_context):
        self.lock = threading.Lock()
        self.zmq_context = zmq_context
        self.zmq_context.setsockopt(zmq.LINGER, 0)
        self.cached_devices = []
        self.cached_hosts = []
        self.device_server = DeviceServer(self.zmq_context)
        self.device_server.create_listener_thread(self._update_devices)
        self.created_interfaces = []

    def _update_devices(self, server_status):
        devices_raw = server_status.get('devices')
        new_devices = []
        for hostname, devices in devices_raw.items():
            for dev_info in devices:
                new_devices.append(DeviceDescription(hostname=hostname, **dev_info))

        hosts_raw = server_status.get('hosts')
        new_hosts = []
        for hostname, host_info in hosts_raw.items():
            new_hosts.append(HostDescription(hostname=hostname, **host_info))

        with self.lock:
            self.cached_devices = new_devices
            self.cached_hosts = new_hosts

    def close(self):
        for interface in self.created_interfaces:
            interface.close()
        self.device_server.close()

    def get_raw_interface(self):
        return self.device_server

    def hosts(self):
        """Returns list of all discovered hosts"""
        return self.cached_hosts

    def devices(self):
        """Returns list of all currently running devices"""
        return self.cached_devices

    def find_device(self, allowed_types):
        """Returns a device of one of indicated types or None if one can't be found"""
        with self.lock:
            devices = self.cached_devices
            found_devices = {}
            for descr in devices:
                if descr.dev_type in allowed_types:
                    found_devices[descr.dev_type] = descr
            for dev_type in allowed_types:
                if dev_type in found_devices:
                    interface = found_devices.get(dev_type).interface(self.zmq_context)
                    return interface
            return None

    def create_listener_thread(self, callback):
        """"Wrapper around DeviceInterface.create_listener_thread"""
        self.device_server.create_listener_thread(callback)


if __name__ == '__main__':
    try:
        server = DeviceServerWorker()
        print('Press Ctrl+C to exit')
        server.run()
    except:
        traceback.print_exc()
