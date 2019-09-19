from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from DeviceServerHeadless import DEVICE_TYPE_INFO, DeviceType

import enum
import queue
import threading
import time
import traceback


REFRESH_DELAY_MS = 100


class NewDeviceForm(QWidget):
    device_created = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        main_layout = QFormLayout(self)

        self.name_lineedit = QLineEdit()
        self.name_lineedit.setPlaceholderText('name')

        self.type_combo = QComboBox()
        for dev_type in DEVICE_TYPE_INFO:
            self.type_combo.addItem(dev_type.name)

        self.req_lineedit = QLineEdit()
        self.req_lineedit.setPlaceholderText('req_port')
        self.req_lineedit.setValidator(QIntValidator())

        self.pub_lineedit = QLineEdit()
        self.pub_lineedit.setPlaceholderText('pub_port')
        self.pub_lineedit.setValidator(QIntValidator())

        start_button = QPushButton('Start')
        start_button.clicked.connect(self._start)

        main_layout.addRow(self.type_combo, start_button)

    def _start(self):
        dev_type_str = self.type_combo.currentText()
        self.device_created.emit(dev_type_str)

class DeviceWidget(QWidget):
    stopped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.dev_descr = None

        main_layout = QHBoxLayout(self)

        self.label = QLabel('')
        main_layout.addWidget(self.label)

        self.stop_button = QPushButton('Stop')
        main_layout.addWidget(self.stop_button)
        self.stop_button.clicked.connect(self._stop)

        self.hide()

    def update(self, dev_descr):
        self.dev_descr = dev_descr
        dev_type_str, _, _ = DEVICE_TYPE_INFO[DeviceType(dev_descr.dev_type)]
        self.label.setText('{} [{}]'.format(dev_descr.name, dev_type_str))
        self.show()

    def _stop(self):
        if self.dev_descr is not None:
            self.stopped.emit(self.dev_descr.name)
        
class ServerWidget(QGroupBox):
    device_created = pyqtSignal(int, str)
    device_stopped = pyqtSignal(str, str)

    def __init__(self, hostname: str, parent=None):
        super().__init__(title=hostname, parent=parent)

        self.host = hostname
        self.device_widgets = []

        main_layout = QVBoxLayout(self)

        new_device_form = NewDeviceForm()
        main_layout.addWidget(new_device_form)
        new_device_form.device_created.connect(self._create_device)

        devices_list = QWidget()
        main_layout.addWidget(devices_list)
        self.devices_list_layout = QVBoxLayout(devices_list)

        main_layout.addStretch()

    def update_devices(self, devices, connected):
        while len(self.device_widgets) < len(devices):
            new_widget = DeviceWidget()
            self.devices_list_layout.addWidget(new_widget)
            self.device_widgets.append(new_widget)
            new_widget.stopped.connect(self._stop_device)

        for i, widget in enumerate(self.device_widgets):
            if i < len(devices):
                dev_descr = devices[i]
                widget.update(dev_descr)
            else:
                widget.hide()

        self.setEnabled(connected)

    @pyqtSlot(str)
    def _stop_device(self, name: str):
        self.device_stopped.emit(name, self.host)

    @pyqtSlot(str)
    def _create_device(self, dev_type_str: str):
        dev_type = DeviceType.__members__.get(dev_type_str)
        self.device_created.emit(dev_type, self.host)


RequestType = enum.Enum('RequestType', [
    'start_process',
    'stop_process',
])

class DevicesWidget(QWidget):
    def __init__(self, device_server, parent=None):
        super().__init__(parent)

        self.device_server = device_server
        self.device_server_raw = device_server.get_raw_interface()
        self.known_servers = {}
        self.requests_queue = queue.SimpleQueue()

        self._create_layout()

        threading.Thread(target=self._process_server_requests, daemon=True).start()

        self.refresh_timer = QTimer()
        self.refresh_timer.setInterval(REFRESH_DELAY_MS)
        self.refresh_timer.timeout.connect(self._refresh)
        self.refresh_timer.start()

    def _create_layout(self):
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        self.servers_layout = QHBoxLayout()
        main_layout.addLayout(self.servers_layout)
        main_layout.addStretch()

    @pyqtSlot(int, str)
    def _start_device(self, dev_type, hostname):
        self.requests_queue.put((RequestType.start_process, dev_type, hostname))

    @pyqtSlot(str, str)
    def _stop_device(self, name, hostname):
        self.requests_queue.put((RequestType.stop_process, name, hostname))

    def _refresh(self):
        try:
            hosts = self.device_server.hosts()
            devices = self.device_server.devices()

            for host_info in hosts:
                hostname = host_info.hostname
                if hostname not in self.known_servers:
                    panel = ServerWidget(hostname)
                    panel.device_created.connect(self._start_device)
                    panel.device_stopped.connect(self._stop_device)
                    self.servers_layout.addWidget(panel)
                    self.known_servers[hostname] = panel

            connected_dict = { host_info.hostname: host_info.connected for host_info in hosts }

            for hostname, panel in self.known_servers.items():
                host_devices = [dev_info for dev_info in devices if dev_info.hostname == hostname]
                connected = connected_dict.get(hostname) or False
                panel.update_devices(host_devices, connected)
        except:
            traceback.print_exc()

    def _process_server_status(self, status):
        self.setEnabled(True)

    def _process_server_requests(self):
        while True:
            request = self.requests_queue.get()
            request_type = request[0]

            try:
                if request_type == RequestType.start_process:
                    _, dev_type, hostname = request
                    self.device_server_raw.start_device(dev_type, hostname)

                elif request_type == RequestType.stop_process:
                    _, name, hostname = request
                    self.device_server_raw.stop_device(name, hostname)

            except ConnectionError:
                self.setDisabled(True)
                print('[devices] no connection to the device server')
                
            except:
                traceback.print_exc()
