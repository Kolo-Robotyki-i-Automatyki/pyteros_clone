from PyQt5 import QtWidgets, QtCore, QtGui

import functools
import json
import os
import random
import socket
import struct
import subprocess
import threading
import time
import weakref
import zmq


CAMERA_SERVER_PORT = 8000

DEFAULT_TIMEOUT_MS = 3000

SIDE_PANEL_WIDTH = 300

STREAM_PORT_MIN = 20000
STREAM_PORT_MAX = 20999

CONFIG_FILE_PATH = os.getenv('HOME') + '/.pyteros/camera_viewer.cfg'


class TimeoutError(Exception):
    pass


video_directions = {
    'none': 0,
    'rotate 90°': 1,
    'rotate 180°': 2,
    'rotate 270°': 3,
    'flip horizontally': 4,
    'flip vertically': 5,
}


class Config:
    def __init__(self):
        self.state = {}

    def get(self, key, default=None):
        return self.state[key] if key in self.state else default

    def set(self, key, value):
        self.state[key] = value

    def load(self):
        self._check_path()
        with open(CONFIG_FILE_PATH, 'r+') as f:
            try:
                self.state = json.load(f)
            except json.JSONDecodeError:
                self.state = {}

    def save(self):
        self._check_path()
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(self.state, f)

    def _check_path(self):
        directory = os.path.abspath(os.path.dirname(CONFIG_FILE_PATH))
        if not os.path.exists(directory):
            os.mkdir(directory)
        open(CONFIG_FILE_PATH, 'a+')

class ScrollWrapper(QtWidgets.QScrollArea):
    def __init__(self, child, parent=None):
        super().__init__(parent)
        self.setWidget(child)
        self.setWidgetResizable(True)
        self.setBackgroundRole(QtGui.QPalette.NoRole)

class StreamViewer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewer_process = None
        self.viewer_widget = QtWidgets.QWidget(parent=self)
        self.aspect_ratio = 1.0
        self.video_direction = 0

        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)

    def _show_stream(self, port, format, video_direction, win_id):
        command = ['./cam_viewer', str(port), format, str(video_direction), str(win_id)]
        # print('gonna run {}'.format(' '.join(command)))
        self.viewer_process = subprocess.Popen(command)
        self.viewer_process.wait()

    def _resize_viewer(self):
        BORDER = 2.0
        w, h = self.width() - BORDER, self.height() - BORDER

        container_aspect = float(w) / float(h)

        if self.video_direction == 1 or self.video_direction == 3:
            aspect = 1.0 / self.aspect_ratio
        else:
            aspect = self.aspect_ratio

        if container_aspect > aspect:
            viewer_w, viewer_h = h * aspect, h
        else:
            viewer_w, viewer_h = w, w / aspect

        self.viewer_widget.setGeometry(
            (w - viewer_w) / 2.0,
            (h - viewer_h) / 2.0,
            viewer_w,
            viewer_h)

    def resizeEvent(self, event):
        self._resize_viewer()

    def start(self, port, encoding, width, height, direction):
        self.aspect_ratio = float(width) / float(height)
        self.video_direction = direction
        self._resize_viewer()

        self.stream_thread = threading.Thread(
            target=self._show_stream,
            args=(port, encoding, direction, int(self.viewer_widget.winId())),
            daemon=True)
        self.stream_thread.start()

    def stop(self):
        try:
            self.viewer_process.terminate()
        except AttributeError:
            pass

class Canvas(QtWidgets.QWidget):

    updateStreams = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.main_layout = QtWidgets.QGridLayout()
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)

        self.updateStreams.connect(self._update_streams)

        self.streams = {}

    # def minimumSizeHint(self):
    #     # return QtCore.QSize(0, 0)
    #     return QtCore.QSize(200, 200)

    def resizeEvent(self, event):
        # print('Canvas resized to {}'.format(self.size()))
        self._reorder_streams()

    def _resize(self, columns, rows):
        # print('Canvas grid: {}x{}'.format(columns, rows))
        pass

    def _reorder_streams(self):
        width, height = float(self.width()), float(self.height())

        size_w = 1
        size_h = 1
        while len(self.streams) > size_w * size_h:
            if (width / size_w) > (height / size_h):
                size_w += 1
            else:
                size_h += 1

        # print('New canvas grid: {}x{}'.format(size_w, size_h))

        for _, viewer in self.streams.items():
            viewer.setParent(self)

        x = 0
        y = 0
        for _, viewer in self.streams.items():
            self.main_layout.addWidget(viewer, y, x)
            x = (x + 1) % size_w
            if x == 0:
                y += 1

    def _start_stream(self, port, encoding, width, height, direction):
        viewer = StreamViewer()
        viewer.start(port, encoding, width, height, direction)

        self.streams[(port, encoding, width, height, direction)] = viewer

    def _update_streams(self, streams):
        stopped_streams = []
        started_streams = []

        for parameters, viewer in self.streams.items():
            if parameters not in streams:
                stopped_streams.append(parameters)

        for parameters in streams:
            if parameters not in self.streams:
                started_streams.append(parameters)

        for parameters in stopped_streams:
            viewer = self.streams.pop(parameters, None)
            if viewer is not None:
                viewer.stop()
            viewer.setParent(None)
            # print("Stopping viewer {}".format(parameters))

        for parameters in started_streams:
            self._start_stream(*parameters)
            # print("Starting viewer {}".format(parameters))

        if len(stopped_streams) > 0 or len(started_streams) > 0:
            self._reorder_streams()

class Client:
    def __init__(self):
        self.ctx = zmq.Context()
        self.used_ports = set()

    def _request(self, host, port, command, timeout=DEFAULT_TIMEOUT_MS):
        s = self.ctx.socket(zmq.REQ)
        s.connect('tcp://{}:{}'.format(host, port))
        s.send_string(command)
        events = s.poll(timeout=timeout)
        if events == 0:
            raise TimeoutError()
        return s.recv().decode('utf-8')

    def streams(self, host, port):
        return json.loads(self._request(host, port, 'STREAMS'))

    def formats(self, host, port):
        return json.loads(self._request(host, port, 'FORMATS'))

    def start(self, host, port, device, encoding, width, height, fps, local_address):
        local_port = None
        while local_port is None or local_port in self.used_ports:
            local_port = random.randint(STREAM_PORT_MIN, STREAM_PORT_MAX)
        self.used_ports.add(local_port)

        request = 'START {} {} {} {} {} {} {}'.format(
            device, encoding, width, height, fps, local_address, local_port)
        return self._request(host, port, request)

    def stop(self, host, port, device):
        request = 'STOP {}'.format(device)
        return self._request(host, port, request)

    def reset(self, host, port):
        request = 'RESET'
        return self._request(host, port, request)

class StreamControlWidget(QtWidgets.QWidget):
    errorOccured = QtCore.pyqtSignal(str)
    fetchedFormats = QtCore.pyqtSignal(dict)
    fetchedStreams = QtCore.pyqtSignal(list)

    def __init__(self, config_ref=None, parent=None):
        super().__init__(parent)

        self.config_ref = config_ref

        self.servers = {}
        self.device_aliases = {}
        self.device_formats = {}
        self.device_status = {}
        self.displayed_streams = []
        self.stream_sets = {}
        self.requested_directions = {}
        self.client = Client()

        self.errorOccured.connect(self._display_error)
        self.fetchedFormats.connect(self._update_device_list)

        self.main_layout = QtWidgets.QFormLayout()
        self.setLayout(self.main_layout)

        self.hostname_lineedit = QtWidgets.QLineEdit()
        self.hostname_lineedit.textChanged.connect(self._edit_hostname)
        self.hostname_lineedit.setPlaceholderText('localhost')

        self.server_list = QtWidgets.QListWidget()
        self.server_list.setMaximumHeight(100)
        self.device_list = QtWidgets.QListWidget()
        
        self.server_name_lineedit = QtWidgets.QLineEdit()
        add_server_button = QtWidgets.QPushButton("Add")
        add_server_button.clicked.connect(self._add_server)
        reset_server_button = QtWidgets.QPushButton("Reset")
        reset_server_button.clicked.connect(self._reset_server)
        remove_server_button = QtWidgets.QPushButton("Remove")
        remove_server_button.clicked.connect(self._remove_server)

        self.device_list.currentItemChanged.connect(self._select_device)
        self.device_list.itemClicked.connect(self._click_device)
        
        stop_stream_button = QtWidgets.QPushButton("Stop")
        stop_stream_button.clicked.connect(self._stop_stream)
        start_stream_button = QtWidgets.QPushButton("Start")
        start_stream_button.clicked.connect(self._start_stream)

        self.device_name_lineedit = QtWidgets.QLineEdit()
        self.device_name_lineedit.textChanged.connect(self._set_device_alias)
        self.encoding_combo = QtWidgets.QComboBox()
        self.encoding_combo.activated.connect(self._pick_encoding)
        self.size_combo = QtWidgets.QComboBox()
        self.size_combo.activated.connect(self._pick_size)
        self.fps_combo = QtWidgets.QComboBox()
        self.fps_combo.activated.connect(self._pick_fps)
        self.direction_combo = QtWidgets.QComboBox()
        for label in video_directions:
            self.direction_combo.addItem(label)
        self.direction_combo.activated.connect(self._update_requested_direction)

        self.stream_set_combo = QtWidgets.QComboBox()
        self.stream_set_select_button = QtWidgets.QPushButton("Select")
        self.stream_set_select_button.clicked.connect(self._select_stream_set)
        self.stream_set_lineedit = QtWidgets.QLineEdit()
        self.stream_set_add_button = QtWidgets.QPushButton("Save")
        self.stream_set_add_button.clicked.connect(self._add_stream_set)

        self.main_layout.addRow("hostname", self.hostname_lineedit)

        self.main_layout.addRow(self.server_list)
        self.main_layout.addRow(reset_server_button, remove_server_button)
        self.main_layout.addRow(self.server_name_lineedit, add_server_button)

        self.main_layout.addRow(self.device_list)
        self.main_layout.addRow(start_stream_button, stop_stream_button)

        self.main_layout.addRow(QtWidgets.QLabel("name"), self.device_name_lineedit)
        self.main_layout.addRow("encoding", self.encoding_combo)
        self.main_layout.addRow("size", self.size_combo)
        self.main_layout.addRow("fps", self.fps_combo)
        self.main_layout.addRow("transformation", self.direction_combo)

        self.main_layout.addRow(QtWidgets.QLabel("Presets"))
        self.main_layout.addRow(self.stream_set_combo, self.stream_set_select_button)
        self.main_layout.addRow(self.stream_set_lineedit, self.stream_set_add_button)

        # load cached server names
        for server_name in config_ref().get('servers', []):
            self._add_named_server(server_name)
        # load hostname
        self.hostname_lineedit.setText(self.config_ref().get('hostname', 'localhost'))
        # load device aliases
        for device, alias in self.config_ref().get('aliases', {}):
            self.device_aliases[(device[0], device[1])] = alias
        # load stream sets
        self.stream_sets = self.config_ref().get('stream_sets', {})
        for name in self.stream_sets:
            self.stream_set_combo.addItem(name)

        self._refresh_devices_in_loop()
        self._refresh_streams_in_loop()

    def _display_error(self, msg):
        print('\nERROR:\n{}\n'.format(msg))

    def _get_ip_address(self, remote_server=None):
        # s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # s.connect((str(remote_server), CAMERA_SERVER_PORT))
        # return s.getsockname()[0]

        return self.hostname_lineedit.text()

    def _refresh_devices_in_loop(self):
        def fetch_formats():
            while True:
                try:
                    formats = {}

                    for server_name in self.servers:
                        try:
                            formats_single_server = self.client.formats(server_name, CAMERA_SERVER_PORT)
                            for device, details in formats_single_server.items():
                                formats[(device, server_name)] = details
                        except TimeoutError:
                            msg = "Couldn't fetch list of formats from \"{}\": connection timed out".format(server_name)
                            self.errorOccured.emit(msg)

                        self.fetchedFormats.emit(formats)
                except Exception as err:
                    print(err)

                time.sleep(1)

            self.errorOccured.emit('Stopped fetching formats')

        threading.Thread(target=fetch_formats, daemon=True).start()

    def _refresh_streams_in_loop(self):
        def fetch_streams():
            while True:
                try:
                    all_streams = {}
                    hostname = self._get_ip_address()

                    for server_name in self.servers:
                        try:
                            streams = self.client.streams(server_name, CAMERA_SERVER_PORT)
                        except TimeoutError:
                            streams = {}
                            msg = "Couldn't fetch list of streams from \"{}\": connection timed out".format(server_name)
                            self.errorOccured.emit(msg)

                        for device, stream_description in streams.items():
                            all_streams[(device, server_name)] = stream_description

                    self.device_status = all_streams

                    updated_displayed_streams = []
                    streams_external_info = []
                    for (device, server), status in all_streams.items():
                        if status is None:
                            continue
                        (destination, port, encoding, width, height, fps) = status
                        if destination == hostname:
                            direction = self.requested_directions.get((device, server), 0)
                            updated_displayed_streams.append((device, server, encoding, width, height, fps, direction))
                            streams_external_info.append((port, encoding, width, height, direction))

                    self.displayed_streams = updated_displayed_streams
                    self.fetchedStreams.emit(streams_external_info)

                    self._update_device_displayed_names()

                except Exception as err:
                    msg = 'Error while fetching streams lists: {}'.format(err)
                    self.errorOccured.emit(msg)

                time.sleep(1)

            self.errorOccured.emit('Stopped fetching streams from')

        threading.Thread(target=fetch_streams, daemon=True).start()

    def _update_device_list(self, formats):
        known_devices = []
        for i in range(self.device_list.count()):
            known_devices.append(self.device_list.item(i).data(1))

        for (device, server), details in formats.items():
            if (device, server) not in known_devices:
                list_item = QtWidgets.QListWidgetItem()
                list_item.setData(1, (device, server))
                self.device_list.addItem(list_item)

            formats_list = []
            for format_description in details:
                encoding = format_description['pixel format']
                for row in format_description['framesizes']:
                    width = row['width']
                    height = row['height']
                    fps = row['fps']

                    formats_list.append((encoding, width, height, fps))
            self.device_formats[(device, server)] = formats_list

        # remove devices from unknown servers
        removed = []
        for i in range(self.device_list.count()):
            if i >= self.device_list.count():
                break
            device_item = self.device_list.item(i)
            (device, server) = device_item.data(1)
            if server not in self.servers:
                self.device_list.takeItem(i)
                i -= 1

        self._update_device_displayed_names()

    def _display_device_info(self):
        item = self.device_list.currentItem()

        self.encoding_combo.clear()
        self.size_combo.clear()
        self.fps_combo.clear()

        self.encoding_combo.setEnabled(True)
        self.size_combo.setEnabled(True)
        self.fps_combo.setEnabled(True)

        if item is None:
            self.device_name_lineedit.setText('')
            self.device_name_lineedit.setPlaceholderText('')
            self.direction_combo.setCurrentIndex(0)
            return

        device, server = item.data(1)
        status = self.device_status.get((device, server), None)
        
        canonic_name = '{}:{}'.format(device, server)
        alias = self.device_aliases.get((device, server), canonic_name)
        self.device_name_lineedit.setText(alias)
        self.device_name_lineedit.setPlaceholderText(canonic_name)

        self.direction_combo.setCurrentIndex(self.requested_directions.get((device, server), 0))

        if status is None:
            formats = self.device_formats.get((device, server), [])

            encodings = set([encoding for (encoding, _, _, _) in formats])

            for encoding in encodings:
                self.encoding_combo.addItem(str(encoding), encoding)

            if len(encodings) > 0:
                self.encoding_combo.setCurrentIndex(0)
                self._pick_encoding(0)
        else:
            destination, port, encoding, width, height, fps = status

            self.encoding_combo.addItem(str(encoding))
            self.size_combo.addItem(str('{}x{}'.format(width, height)), (width, height))
            self.fps_combo.addItem(str(fps))

            self.encoding_combo.setEnabled(False)
            self.size_combo.setEnabled(False)
            self.fps_combo.setEnabled(False)

    def _edit_hostname(self):
        hostname = str(self.hostname_lineedit.text()).strip()
        if (len(hostname) > 0):
            self.config_ref().set('hostname', hostname)

    def _add_server(self):
        server_name = str(self.server_name_lineedit.text())
        self._add_named_server(server_name)

        servers = self.config_ref().get('servers', [])
        if server_name not in servers:
            servers.append(server_name)
        self.config_ref().set('servers', servers)

    def _add_named_server(self, server_name):
        if len(server_name) == 0 or server_name in self.servers:
            self.errorOccured.emit('Server "{}" already on the list'.format(server_name))
            return

        self.server_list.addItem(server_name)
        self.servers[server_name] = {}

    def _reset_server(self):
        if len(self.server_list) == 0:
            return

        server_name = str(self.server_list.currentItem().text())
        self.client.reset(server_name, CAMERA_SERVER_PORT)

    def _remove_server(self):
        if len(self.server_list) == 0:
            return

        server_item = self.server_list.currentItem()
        name = str(server_item.text())
        self.server_list.takeItem(self.server_list.currentRow())
        self.servers.pop(name, None)

        servers = self.config_ref().get('servers', [])
        if name in servers:
            servers.remove(name)
        self.config_ref().set('servers', servers)

    def _start_stream(self):
        encoding = self.encoding_combo.currentData()
        width, height = self.size_combo.currentData()
        fps = self.fps_combo.currentData()

        device, server = self.device_list.currentItem().data(1)

        self._start_stream_from_parameters(device, server, encoding, width, height, fps)

    def _start_stream_from_parameters(self, device, server, encoding, width, height, fps):
        address = self._get_ip_address()

        response = self.client.start(server, CAMERA_SERVER_PORT, device, encoding, width, height, fps, address)

        print('Response from the server:')
        print(response)

    def _stop_stream(self):
        device, server = self.device_list.currentItem().data(1)

        self._stop_stream_from_parameters(device, server)

    def _stop_stream_from_parameters(self, device, server):
        response = self.client.stop(server, CAMERA_SERVER_PORT, device)

        print('Response from the server:')
        print(response)

    def _select_device(self):
        device, server = self.device_list.currentItem().data(1)
        name = self.device_aliases.get((device, server), '')

        self.device_name_lineedit.setPlaceholderText(name)
        self.device_name_lineedit.setText(name)

        formats = self.device_formats[(device, server)]

        self._display_device_info()

    def _click_device(self, item):
        self._display_device_info()

    def _set_device_alias(self):
        device, server = self.device_list.currentItem().data(1)

        alias = str(self.device_name_lineedit.text()).strip()
        if len(alias) == 0:
            alias = '{}:{}'.format(device, server)

        self.device_aliases[(device, server)] = alias

        self._update_device_displayed_names()

        aliases_list = [[[device, server], alias] for (device, server), alias in self.device_aliases.items()]
        self.config_ref().set('aliases', aliases_list)

    def _update_device_displayed_names(self):
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)

            (device, server) = item.data(1)
            alias = self.device_aliases.get((device, server), '{}:{}'.format(device, server))

            status = self.device_status.get((device, server), None)

            if status is None:
                displayed_name = alias
            else:
                (destination, _,  _, _, _, _) = status
                displayed_name = '{}  🠪  {}'.format(alias, destination)

            item.setText(displayed_name)

    def _pick_encoding(self, index):
        device, server = self.device_list.currentItem().data(1)

        formats = self.device_formats[(device, server)]

        encoding = self.encoding_combo.currentData()

        sizes = set([(w, h) for (enc, w, h, _) in formats if enc == encoding])

        self.size_combo.clear()
        for (w, h) in sizes:
            self.size_combo.addItem('{}x{}'.format(w, h), (w, h))

        if len(sizes) > 0:
            self.size_combo.setCurrentIndex(0)
            self._pick_size(0)

    def _pick_size(self, index):
        device, server = self.device_list.currentItem().data(1)

        formats = self.device_formats[(device, server)]

        encoding = self.encoding_combo.currentData()
        size = self.size_combo.currentData()

        available_fps = set([f for (enc, w, h, f) in formats if enc == encoding and (w, h) == size])
        
        self.fps_combo.clear()
        for fps in available_fps:
            self.fps_combo.addItem(str(fps), fps)

        if len(available_fps) > 0:
            self.fps_combo.setCurrentIndex(0)
            self._pick_fps(0)

    def _pick_fps(self, index):
        pass

    def _update_requested_direction(self):
        device, server = self.device_list.currentItem().data(1)
        direction = video_directions[str(self.direction_combo.currentText())]

        self.requested_directions[(device, server)] = direction

    def _select_stream_set(self):
        name = str(self.stream_set_combo.currentText())
        streams = self.stream_sets.get(name, [])

        self.stream_set_lineedit.setPlaceholderText(name)

        required = [(device, server) for (device, server, _, _, _, _, _) in streams]

        for (device, server, _, _, _, _, _) in self.displayed_streams:
            if (device, server) not in required:
                self._stop_stream_from_parameters(device, server)

        self.displayed_streams = []

        for (device, server, encoding, width, height, fps, direction) in streams:
            self.requested_directions[(device, server)] = direction
            self._start_stream_from_parameters(device, server, encoding, width, height, fps)

        self._display_device_info()

    def _add_stream_set(self):
        name = str(self.stream_set_lineedit.text()).strip()

        if len(name) == 0:
            name = str(self.stream_set_lineedit.placeholderText()).strip()

        if len(name) == 0:
            return

        if name not in self.stream_sets:
            self.stream_set_combo.addItem(name)

        self.stream_sets[name] = self.displayed_streams
        self.config_ref().set('stream_sets', self.stream_sets)

class CameraViewer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.config = Config()
        self.config.load()

        self.canvas = Canvas()
        self.server_list = StreamControlWidget(weakref.ref(self.config))

        self.main_layout = QtWidgets.QHBoxLayout()
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self._autosave_config()

        # sidebar
        show_hide_server_list_button = QtWidgets.QPushButton()
        show_hide_server_list_button.clicked.connect(self._show_hide_server_list)
        show_hide_server_list_button.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum))
        self.main_layout.addWidget(show_hide_server_list_button)
        self.main_layout.setStretch(0, 0)

        self.main_layout.addWidget(self.server_list)
        self.main_layout.setStretch(1, 0)
        self.server_list.fetchedStreams.connect(self._update_streams)

        # canvas
        self.main_layout.addWidget(self.canvas)
        self.main_layout.setStretch(2, 1)

    def _show_hide_server_list(self):
        if self.server_list.isHidden():
            self.server_list.show()
        else:
            self.server_list.hide()

    def _update_streams(self, streams):
        self.canvas.updateStreams.emit(streams)

    def _autosave_config(self):
        def save_config_in_loop():
            while True:
                try:
                    self.config.save()
                except Exception as err:
                    print(err)

                time.sleep(5)

        threading.Thread(target=save_config_in_loop, daemon=True).start()
