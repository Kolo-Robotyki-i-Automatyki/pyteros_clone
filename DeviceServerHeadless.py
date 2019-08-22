#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 26 09:54:02 2018

This code was originally written by Tomasz Kazimierczuk for LUMS - Laboratory
of Ultrafast MagnetoSpectroscopy at Faculty of Physics, University of Warsaw

"""

from PyQt5 import Qt, QtCore
import zmq

from devices.zeromq_device import *

from collections import namedtuple
import csv
import importlib
import random
import re
import socket
import sys
import time
import traceback


DEVICE_TYPES_FILE = 'devices.csv'
LOCAL_DEVICES_FILE = 'local_devices.txt'

FETCH_PROCESS_OUTPUT_DELAY_S = 0.1

PROCESS_AUTOSTART_DELAY_MS = 200

PORT_RANGE = (30000, 40000)
DEVICE_SERVER_PUB_PORT = 23412
DEVICE_SERVER_REQ_PORT = 23413
HEARTBEAT_SEND_PORT = 14452
HEARTBEAT_RECV_PORT = 14453
HEARTBEAT_DELAY_S = 1.0
FETCH_PROCESSES_LIST_DELAY_S = 0.1


class ZMQ_Listener(QtCore.QObject):
    """ A class to implement a thread listening for stdout/stderr 
    from other thread via a ZeroMQ PUB/SUB socket pair """
    msg_info = QtCore.pyqtSignal(str)
    msg_err = QtCore.pyqtSignal(str)

    def __init__(self, socket):
        QtCore.QObject.__init__(self)
        self.socket = socket
        self.continue_running = True
         
    def loop(self):
        while self.continue_running:
            try:
                [address, contents] = self.socket.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.error.Again:
                time.sleep(FETCH_PROCESS_OUTPUT_DELAY_S)
                continue

            if address == b'stderr':
                self.msg_err.emit(contents.decode('ascii'))
            else:
                self.msg_info.emit(contents.decode('ascii'))


class Process(QtCore.QObject):
    def __init__(self, req_port: int = 0, pub_port: int = 0, process_class = None, create_daemonic: bool = True, **kwargs):
        super().__init__()

        self.lock = threading.Lock()

        self.req_port = req_port
        self.pub_port = pub_port
        self.process_class = process_class
        self.create_daemonic = create_daemonic
        self.kwargs = kwargs
        
        zmq_context = zmq.Context()
        self.sub_socket = zmq_context.socket(zmq.SUB)
        self.sub_socket.connect("tcp://localhost:%s" % str(pub_port))
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'std')
        
        self.process = None
        
        def appendErr(text):
            print(text)
        
        def appendInfo(text):
            print(text)

        self.listener_thread = QtCore.QThread(self)
        self.listener = ZMQ_Listener(self.sub_socket)
        self.listener.moveToThread(self.listener_thread)
        self.listener_thread.started.connect(self.listener.loop)
        self.listener.msg_info.connect(appendInfo)
        self.listener.msg_err.connect(appendErr)
        self.listener_thread.start()

        self.monitor_process_timer = QtCore.QTimer(self)
        self.monitor_process_timer.timeout.connect(self._check_on_process)

        self.start_process()

    def __del__(self):
        self.listener.continue_running = False
        self.listener_thread.quit()
        self.listener_thread.wait()
        self.stop_process()

    def start_process(self):
        with self.lock:
            self._start_process()

    def _start_process(self):
        try:
            self.process = self.process_class(req_port=self.req_port, pub_port=self.pub_port, **self.kwargs)
            self.process.daemon = self.create_daemonic
            self.process.start()
            self.monitor_process_timer.start(PROCESS_AUTOSTART_DELAY_MS)
        except Exception as e:
            print('Process._start_process(): {}'.format(e))

    def stop_process(self):
        with self.lock:
            self._stop_process()

    def _stop_process(self):
        try:       
            self.monitor_process_timer.stop()

            if self.process is not None:
                self.process.terminate()
                self.process.join()
                self.process = None
        except Exception as e:
            print('Process._stop_process(): {}'.format(e))

    def _check_on_process(self):
        with self.lock:
            if self.process is not None:
                if not self.process.is_alive():
                    print('Process._check_on_process(): restarting {}'.format(self.process_class))
                    self._stop_process()
                    self._start_process()

class _DeviceServerWorker(DeviceWorker):
    def __init__(self, req_port, pub_port):
        super().__init__(req_port=req_port, pub_port=pub_port)
        load_device_types()

    def init_device(self):
        super().init_device()

        self.qt_app = QtCore.QCoreApplication(sys.argv)

        self.local_processes_lock = threading.Lock()
        self.hosts_lock = threading.Lock()

        self.device_types = get_device_types()

        self.hostname = socket.gethostname()
        self.local_processes = {}

        self.remote_hosts = {}
        self.remote_processes = {}

        with open(LOCAL_DEVICES_FILE) as f:
            for dev_type in f:
                dev_type = dev_type.strip()
                if len(dev_type) > 0:
                    self._start_local_process(dev_type.replace(' ', '_'), dev_type)

        threading.Thread(target=self._send_heartbeat, daemon=True).start()        
        threading.Thread(target=self._recv_heartbeat, daemon=True).start()

    def log(self, msg: str):
        print('[_DeviceServer] {}'.format(msg))

    @remote
    def get_all_hosts(self):
        hosts = { self.hostname: 'localhost' }
        with self.hosts_lock:
            for hostname, (addr, _) in self.remote_hosts.items():
                hosts[hostname] = addr
        return hosts

    @remote
    def get_local_processes(self):
        result = []
        with self.local_processes_lock:
            for name, (_, dev_type, pub, req) in self.local_processes.items():
                result.append((name, dev_type, self.hostname, pub, req))
        return result

    @remote
    def get_all_processes(self):
        result = self.get_local_processes()
        with self.hosts_lock:
            for host, process_list in self.remote_processes.items():
                for name, dev_type, _, pub, req in process_list:
                    result.append((name, dev_type, host, pub, req))
        return result

    def _get_unique_name(self, name: str):
        with self.local_processes_lock:
            if name not in self.local_processes:
                return name

            if len(name) == 0:
                base, number = 'dev', 1
            elif re.match(r'^\d+$', name) is not None:
                base, number = 'dev', int(name)
            elif re.match(r'^\D+$', name) is not None:
                base, number = name, 1
            else:
                match = re.match(r'(^.*\D)(\d+$)', name)
                base, number = match[1], int(match[2])

            while (name + str(number)) in self.local_processes:
                number += 1

            return name + str(number)

    @remote
    def start_process(self, name: str, dev_type: str, host: str = None, **kwargs):
        try:
            if host is None or host == self.hostname:                
                self._start_local_process(name, dev_type, **kwargs)
            else:
                self._start_remote_process(name, dev_type, host, **kwargs)
        except Exception as e:
            self.log('start_process(): {}'.format(e))

    def _start_local_process(self, name: str, dev_type: str, **kwargs):
        if dev_type not in self.device_types:
            self.log('unrecognized device type "{}"'.format(dev_type))
            return

        if 'pub_port' not in kwargs or 'req_port' not in kwargs:
            used_ports = set()
            with self.local_processes_lock:
                for _, (_, _, pub, req) in self.local_processes.items():
                    used_ports.add(pub)
                    used_ports.add(req)

                for param in ['pub_port', 'req_port']:
                    while True:
                        port = random.randrange(*PORT_RANGE)
                        if port not in used_ports:
                            used_ports.add(port)
                            kwargs[param] = port
                            break

        pub_port = kwargs['pub_port']
        req_port = kwargs['req_port']

        worker_path, _ = self.device_types[dev_type]
        worker_module, worker_name = worker_path.rsplit('.', 1)
        worker_class = getattr(importlib.import_module(worker_module), worker_name)

        name = self._get_unique_name(name)

        with self.local_processes_lock:
            self.log('creating process "{}": {}'.format(name, dev_type))

            process = Process(process_class=worker_class, **kwargs)
            self.local_processes[name] = (process, dev_type, pub_port, req_port)

    def _start_remote_process(self, name: str, dev_type: str, host: str, **kwargs):
        def worker(address, name, dev_type, host, kwargs):
            interface = _DeviceServer(host=address)
            interface.start_process(name, dev_type, host, **kwargs)

        with self.hosts_lock:
            if host not in self.remote_hosts:
                return
            address, _ = self.remote_hosts[host]

        threading.Thread(target=worker, args=(address, name, dev_type, host, kwargs)).start()

    @remote
    def stop_process(self, name: str, host: str = None):
        try:
            if host is None or host == self.hostname:
                self._stop_local_process(name)
            else:
                self._stop_remote_process(name, host)
        except Exception as e:
            self.log('stop_process(): {}'.format(e))

    def _stop_local_process(self, name: str):
        with self.local_processes_lock:
            if name not in self.local_processes:
                self.log('"{}" is not currently running'.format(name))
                return

            self.log('stopping process "{}"'.format(name))

            process, _, _, _ = self.local_processes[name]
            process.stop_process()
            del self.local_processes[name]

    def _stop_remote_process(self, name: str, host: str):
        def worker(address, name, host):
            interface = _DeviceServer(host=address)
            interface.stop_process(name, host)

        with self.hosts_lock:
            if host not in self.remote_hosts:
                return
            address, _ = self.remote_hosts[host]

        threading.Thread(target=worker, args=(address, name, host)).start()

    def _send_heartbeat(self):       
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        send_sock.bind(('', HEARTBEAT_SEND_PORT))

        while True:
            try:
                msg = self.hostname.encode('ascii')
                send_sock.sendto(msg, ('<broadcast>', HEARTBEAT_RECV_PORT))
                time.sleep(HEARTBEAT_DELAY_S)
            except Exception as e:
                self.log('_send_heartbeat(): {}'.format(e))

    def _recv_heartbeat(self):
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        recv_sock.bind(('', HEARTBEAT_RECV_PORT))

        while True:
            try:
                msg, (addr, port) = recv_sock.recvfrom(1024)
                hostname = msg.decode('ascii')
                if hostname == self.hostname:
                    continue

                check_host_thread = None
                with self.hosts_lock:
                    if hostname not in self.remote_hosts:
                        interface = _DeviceServer(host=addr)
                        self.remote_hosts[hostname] = (addr, interface)
                        self.remote_processes[hostname] = []
                        check_host_thread = threading.Thread(target=self._check_remote_host, args=(hostname,), daemon=True)
                if check_host_thread is not None:
                    check_host_thread.start()
            
            except Exception as e:
                self.log('_recv_heartbeat(): {}'.format(e))

    def _check_remote_host(self, host: str):
        while True:
            try:
                with self.hosts_lock:
                    if host not in self.remote_hosts:
                        return
                    _, interface = self.remote_hosts[host]
                processes = interface.get_local_processes()
                with self.hosts_lock:
                    self.remote_processes[host] = processes

                time.sleep(FETCH_PROCESSES_LIST_DELAY_S)
            except ConnectionError:
                self.log('_check_remote_host(): {} is not responding'.format(host))
            except Exception as e:
                self.log('_check_remote_host(): {}: {}'.format(type(e), e))

@include_remote_methods(_DeviceServerWorker)
class _DeviceServer(DeviceOverZeroMQ):
    def __init__(self, host):
        super().__init__(req_port=DEVICE_SERVER_REQ_PORT, pub_port=DEVICE_SERVER_PUB_PORT, host=host)
 
################################################################################

_known_device_types = None

def load_device_types():
    global _known_device_types

    with open(DEVICE_TYPES_FILE) as device_types_file:
        device_types = {}
        for row in csv.reader(device_types_file):
            if len(row) != 3:
                continue
            name, worker_path, interface_path = row
            device_types[name] = (worker_path, interface_path)
        _known_device_types = device_types

def get_device_types():
    global _known_device_types

    if _known_device_types is None:
        load_device_types()
    return _known_device_types


_local_dev_server = None
_local_server_lock = None

Device = namedtuple('Device', ['name', 'type', 'host', 'req_port', 'pub_port'])

def _safe_call(default):
    def decorator(function):
        def wrapper(*args, **kwargs):
            try:
                with _local_server_lock:
                    return function(*args, **kwargs)
            except Exception as e:
                print('{}(): {} {}'.format(function.__name__, type(e), e))
                return default
        return wrapper
    return decorator

@_safe_call({})
def get_hosts():
    return _local_dev_server.get_all_hosts()

@_safe_call([])
def get_devices():
    devices_raw = _local_dev_server.get_all_processes()
    devices = []
    for name, dev_type, hostname, pub_port, req_port in devices_raw:
        devices.append(Device(name=name, type=dev_type, host=hostname, req_port=req_port, pub_port=pub_port))
    return devices

@_safe_call(None)
def get_proxy(device: Device):
    address = _local_dev_server.get_all_hosts()[device.host]
    _, class_path = get_device_types()[device.type]
    return create_obj_from_path(class_path, host=address, req_port=device.req_port, pub_port=device.pub_port)

@_safe_call(None)
def start_device(name: str, dev_type: str, host: str = None, **kwargs):
    _local_dev_server.start_process(name, dev_type, host, **kwargs)

@_safe_call(None)
def stop_device(name: str, host: str = None):
    _local_dev_server.stop_process(name, host)


if __name__ == '__main__':
    app = QtCore.QCoreApplication(sys.argv)

    dev_server_process = Process(
        process_class=_DeviceServerWorker,
        pub_port=DEVICE_SERVER_PUB_PORT,
        req_port=DEVICE_SERVER_REQ_PORT,
        create_daemonic=False
    )
    
    app.exec_()
else:
    _local_dev_server = _DeviceServer(host='localhost')
    _local_server_lock = threading.Lock()
