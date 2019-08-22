from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from DeviceServerHeadless import *

import threading


REFRESH_DELAY_MS = 100


class NewDeviceForm(QWidget):
    device_created = pyqtSignal(str, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        main_layout = QFormLayout(self)

        self.name_lineedit = QLineEdit()
        self.name_lineedit.setPlaceholderText('name')

        self.type_combo = QComboBox()
        for dev_type in get_device_types():
            self.type_combo.addItem(dev_type)

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
        dev_type = self.type_combo.currentText()
        name = self.name_lineedit.text()
        req_port = int(self.req_lineedit.text() or '0')
        pub_port = int(self.pub_lineedit.text() or '0')

        self.device_created.emit(name, dev_type, req_port, pub_port)

class DeviceWidget(QWidget):
    stopped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.name = ''

        main_layout = QHBoxLayout(self)

        self.label = QLabel('')
        main_layout.addWidget(self.label)

        self.stop_button = QPushButton('Stop')
        main_layout.addWidget(self.stop_button)
        self.stop_button.clicked.connect(self._stop)

        self.hide()

    def update(self, device: Device):
        self.name = device.name
        self.label.setText('{} [{}]'.format(device.name, device.type))
        self.show()

    def _stop(self):
        self.stopped.emit(self.name)
        
class ServerWidget(QGroupBox):
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

    def update_devices(self, devices):
        while len(self.device_widgets) < len(devices):
            new_widget = DeviceWidget()
            self.devices_list_layout.addWidget(new_widget)
            self.device_widgets.append(new_widget)
            new_widget.stopped.connect(self._stop_device)

        for i, widget in enumerate(self.device_widgets):
            if i < len(devices):
                dev = devices[i]
                widget.update(dev)
            else:
                widget.hide()

    @pyqtSlot(str)
    def _stop_device(self, name: str):
        threading.Thread(
            target=stop_device,
            daemon=True,
            kwargs={
                'name': name,
                'host': self.host,
            }
        ).start()

    @pyqtSlot(str, str, int, int)
    def _create_device(self, name: str, dev_type: str, req_port: int, pub_port: int):
        kwargs = {
            'name': name or dev_type.lower().replace(' ', '_'),
            'dev_type': dev_type,
            'host': self.host,
        }
        if req_port != 0:
            kwargs['req_port'] = req_port
        if pub_port != 0:
            kwargs['pub_port'] = pub_port

        threading.Thread(
            target=start_device,
            daemon=True,
            kwargs=kwargs
        ).start()


class DevicesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.lock = threading.Lock()

        self.known_servers = {}

        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        self.servers_layout = QHBoxLayout()
        main_layout.addLayout(self.servers_layout)

        main_layout.addStretch()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh)
        self.refresh_timer.start(REFRESH_DELAY_MS)

    def _refresh(self):
        hosts = get_hosts()

        with self.lock:
            for hostname, _ in hosts.items():
                if hostname not in self.known_servers:
                    panel = ServerWidget(hostname=hostname)
                    self.servers_layout.addWidget(panel)
                    self.known_servers[hostname] = panel

        all_devices = get_devices()
        with self.lock:
            for hostname, panel in self.known_servers.items():
                devices = [dev for dev in all_devices if dev.host == hostname]
                panel.update_devices(devices)
