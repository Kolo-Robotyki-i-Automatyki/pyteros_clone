from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, \
    QLabel, QCheckBox, QPushButton, QLineEdit
from PyQt5.QtCore import pyqtSignal, QThread

import threading
from typing import List
import subprocess

from devices.cameras import CameraServer
from settings import Settings


video_transforms = [
    'no transform',
    'rotate 90°',
    'rotate 180°',
    'rotate 270°',
    'flip horizontally',
    'flip vertically',
]


class CameraControl(QWidget):
    def __init__(self, dev_name: str, server_name: str, modes : List,
            host: str, port: int, server, parent=None):
        super().__init__(parent)

        self.dev_name = dev_name
        self.server_name = server_name
        self.server = server
        self.host = host
        self.port = port

        if len(modes) == 0:
            raise Exception('camera "{}" has no available modes'.format(name))
        self.modes = modes
        self.mode_idx = 0

        self.viewer = None
        self.window_open = False


        self.flip = 0
        self.button_flip = QPushButton('')
        self.button_flip.clicked.connect(self._cycle_flip)

        self.button_quality = QPushButton('')
        self.button_quality.clicked.connect(self._cycle_mode)

        self.checkbox_record = QCheckBox('record')
        
        self.checkbox_stream = QCheckBox('stream')
        self.checkbox_stream.setChecked(True)

        self.capture_on = False
        self.button_start_stop = QPushButton('')
        self.button_start_stop.clicked.connect(self._toggle_capture)

        self._update_ui()


        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        def column(widgets):
            col = QWidget()
            col.setLayout(QVBoxLayout())
            for w in widgets:
                col.layout().addWidget(w)
            main_layout.addWidget(col)

        column([
            QLabel('Server: {}'.format(server_name)),
            QLabel('Device: {}'.format(dev_name))
        ])
        column([
            self.button_quality,
            self.button_flip
        ])
        column([
            self.checkbox_record,
            self.checkbox_stream
        ])
        column([
            self.button_start_stop
        ])

    def is_recording(self):
        return self.checkbox_record.isChecked()

    def is_streaming(self):
        return self.checkbox_stream.isChecked()

    def update_hostname(self, hostname: str):
        self.host = hostname

    def _update_ui(self):
        self.button_flip.setText(video_transforms[self.flip])

        (fmt, w, h, f) = self.modes[self.mode_idx]
        self.button_quality.setText('{} {}x{} {} fps'.format(fmt, w, h, f))

        if not self.is_streaming() and not self.is_recording():
            self.button_start_stop.setEnabled(False)
        else:
            self.button_start_stop.setEnabled(True)

        if self.capture_on:
            self.checkbox_stream.setEnabled(False)
            self.checkbox_record.setEnabled(False)
            self.button_start_stop.setText('STOP')
        else:
            self.checkbox_stream.setEnabled(True)
            self.checkbox_record.setEnabled(True)
            self.button_start_stop.setText('START')

    def _cycle_flip(self):
        self.flip = (self.flip + 1) % len(video_transforms)
        self._update_ui()

    def _cycle_mode(self):
        self.mode_idx = (self.mode_idx + 1) % len(self.modes)
        self._update_ui()

    def _toggle_capture(self):
        self.capture_on = not self.capture_on
        if not self.is_recording() and not self.is_streaming():
            self.capture_on = False

        self._update_ui()

        self._set_camera_status()

    def _set_camera_status(self):
        try:
            if self.capture_on:
                fmt, width, height, fps = self.modes[self.mode_idx]
                self.server.set_camera_status(
                    dev_name=self.dev_name,
                    is_recording=self.is_recording(),
                    is_streaming=self.is_streaming(),
                    fmt=fmt,
                    width=width,
                    height=height,
                    framerate=fps,
                    host=self.host,
                    port=self.port
                )
                if self.is_streaming():
                    self._open_window()
            else:
                self.server.set_camera_status(
                    dev_name=self.dev_name,
                    is_recording=False,
                    is_streaming=False
                )
        except Exception as e:
            print(e)

    def _close_window(self):
        try:
            self.viewer.kill()
        except:
            pass

        self.viewer = None

    def _open_window(self):
        port = self.port
        pixel_format, _, _, _ = self.modes[self.mode_idx]
        
        print('[streaming] running viewer for {} {}'.format(pixel_format, port))
        
        self._close_window()

        pipeline = ['gst-launch-1.0.exe -vvv udpsrc port={}'.format(port)]
        if pixel_format in ['YUYV', 'MJPG']:
            pipeline.extend([
                'application/x-rtp,media=video,clock-rate=90000,encoding-name=JPEG,payload=26',
                'rtpjpegdepay', 'jpegdec'
            ])
        elif pixel_format in ['H264']:
            pipeline.extend([
                'application/x-rtp,encoding-name=H264,payload=96',
                'rtph264depay', 'avdec_h264'
            ])
        else:
            return
        pipeline.extend([
            'videoflip video-direction={}'.format(self.flip), 'queue', 'autovideosink'
        ])

        cmd = ' ! '.join(pipeline)
        print('[streaming] cmd = "{}"'.format(cmd))

        self.viewer = subprocess.Popen(cmd.split(), shell=False)


class SettingsPanel(QWidget):
    updated_host = pyqtSignal(str)

    def __init__(self, default_hostname: str, parent=None):
        super().__init__(parent)

        main_layout = QFormLayout()
        self.setLayout(main_layout)

        self.host_lineedit = QLineEdit(default_hostname)
        self.host_lineedit.editingFinished.connect(self._update_host)
        main_layout.addRow(QLabel('Public ip:'), self.host_lineedit)

    def _update_host(self):
        host = self.host_lineedit.text()
        self.updated_host.emit(host)


class DeviceLoader(QThread):
    finished = pyqtSignal(list)

    def __init__(self, servers, parent=None):
        super().__init__(parent)
        self.servers = servers

    def __del__(self):
        self.wait()

    def run(self):
        all_devices = []

        # print('detecting devices...')

        next_port = 16389
        for server in self.servers:
            try:
                devices = server.get_devices()
                for dev_name in devices:
                    modes = server.get_modes(dev_name)
                    all_devices.append((
                        dev_name,
                        modes,
                        next_port,
                        server
                    ))
                    next_port += 1
            except Exception as e:
                print(e)

        # print('done!')

        self.finished.emit(all_devices)


class StreamingWidget(QWidget):
    def __init__(self, connected_devices={}, parent=None):
        super().__init__(parent)

        self.camera_servers = []
        try:
            for name, dev in {k: v for k, v in connected_devices.items() if isinstance(v, CameraServer)}.items():
                self.camera_servers.append(dev)
                print('[streaming] detected camera server "{}"'.format(name))
        except Exception as e:
            print(e)

        self.settings = Settings('streaming_widget')

        self.hostname = self.settings.get('hostname', '127.0.0.1')

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        settings_panel = SettingsPanel(self.hostname)
        settings_panel.updated_host.connect(self._update_host)
        main_layout.addWidget(settings_panel)

        # TODO this doesn't run in paralell as intended, fix it!
        self.camera_widgets_container = QWidget()
        self.camera_widgets_container.setLayout(QVBoxLayout())
        main_layout.addWidget(self.camera_widgets_container)

        main_layout.addStretch()


        loader = DeviceLoader(self.camera_servers)
        loader.finished.connect(self._add_devices_from_list)
        loader.start()

        self._add_device('chuj', 'ehhh', [('fake', 12, 34, 'lol')], '127.0.0.1', 9999, None)

    def _add_devices_from_list(self, devices):
        for dev_name, modes, port, server in devices:
            try:
                server_name = server.get_name()
                self._add_device(dev_name, server_name, modes, self.hostname, port, server)
            except Exception as e:
                print(e)

    def _add_device(self, dev_name: str, server_name: str, modes, hostname: str, port: int, server):
        self.camera_widgets_container.layout().addWidget(
            CameraControl(dev_name, server_name, modes, hostname, port, server)
        )

    def _update_host(self, hostname: str):
        print('[streaming] hostname changed to {}'.format(hostname))

        self.settings.set('hostname', hostname)

        for cam in self.findChildren(CameraControl):
            cam.update_hostname(hostname)
