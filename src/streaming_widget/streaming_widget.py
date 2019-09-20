from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, \
    QLabel, QCheckBox, QPushButton, QLineEdit, QApplication, QComboBox
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThread, QObject, QTimer

import threading
from typing import List
import subprocess

from devices.cameras import CameraServer
from DeviceServerHeadless import DeviceServer, DeviceType
from src.common.settings import Settings
import time


video_transforms = [
    'no transform',
    'rotate 90°',
    'rotate 180°',
    'rotate 270°',
    'flip horizontally',
    'flip vertically',
]


class CommandRunner(QObject):
    finished = pyqtSignal()

    def __init__(self, cmd):
        super().__init__()
        self.should_exit = False
        self.cmd = cmd

    @pyqtSlot()
    def run(self):
        process = subprocess.Popen(self.cmd.split(), shell=False)

        while True:
            time.sleep(0.2)
            QApplication.instance().processEvents()

            if process.poll() is not None:
                break
            if self.should_exit:
                break

        try:
            process.kill()
        except:
            pass

        self.finished.emit()
        QThread.currentThread().exit()

    @pyqtSlot()
    def close(self):
        self.should_exit = True


class CameraControl(QWidget):
    close_viewer = pyqtSignal()
    camera_name_updated = pyqtSignal(str, str)

    def __init__(self, dev_name: str, server_name: str, modes : List,
            host: str, port: int, server, parent=None):
        super().__init__(parent)

        self.dev_name = dev_name
        self.server_name = server_name
        self.server = server
        self.host = host
        self.port = port

        self.camera_name = ''

        if len(modes) == 0:
            raise Exception('camera "{}" has no available modes'.format(name))

        self.available_formats = list(set([fmt for (fmt, _, _, _) in modes]))
        self.modes = {}
        for fmt in self.available_formats:
            modes_this_fmt = [(w, h, f) for (this_fmt, w, h, f) in modes if this_fmt == fmt]
            try:
                max_w = {
                    'YUYV': 640,
                    'MJPG': 800,
                    'H264': 1280, 
                }[fmt]
            except:
                max_w = 0
            modes_limited = [(w, h, f) for (w, h, f) in modes_this_fmt if w <= max_w]
            modes_sorted = sorted(list(set(modes_limited)))

            if len(modes_sorted) > 0:
                self.modes[fmt] = modes_sorted
        
        self.format = None
        self.mode = None

        self.viewer = None
        self.viewer_thread = None
        self.window_open = False

        self.lineedit_name = QLineEdit(self.camera_name)
        self.lineedit_name.setPlaceholderText(self._get_dev_str())
        self.lineedit_name.editingFinished.connect(self._update_camera_name)

        self.flip = 0
        self.button_flip = QPushButton('')
        self.button_flip.clicked.connect(self._cycle_flip)

        self.combo_format = QComboBox()
        self.combo_format.currentIndexChanged.connect(self._select_format)
        self.combo_quality = QComboBox()
        self.combo_quality.currentIndexChanged.connect(self._select_quality)

        for fmt in self.available_formats:
            self.combo_format.addItem(fmt)
        self._refresh_quality()

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
            self.lineedit_name,
            QLabel('Server: {}'.format(server_name)),
            QLabel('Device: {}'.format(dev_name))
        ])
        column([
            self.combo_format,
            self.combo_quality,
            self.button_flip
        ])
        column([
            self.checkbox_record,
            self.checkbox_stream
        ])
        column([
            self.button_start_stop
        ])


        self.server_update_timer = QTimer()
        self.server_update_timer.setInterval(1000)
        self.server_update_timer.setSingleShot(False)
        self.server_update_timer.timeout.connect(self._apply_server_update)
        self.server_update_timer.start()

    def load_data(self, data):
        id_str = self._get_dev_str()
        if id_str in data:
            self.camera_name = data[id_str]
            self.lineedit_name.setText(self.camera_name)

    def is_recording(self):
        return self.checkbox_record.isChecked()

    def is_streaming(self):
        return self.checkbox_stream.isChecked()

    def update_hostname(self, hostname: str):
        self.host = hostname

    def _update_ui(self):
        self.button_flip.setText(video_transforms[self.flip])

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

    def _get_dev_str(self):
        return '{}:{}'.format(self.dev_name, self.server_name)

    def _update_camera_name(self):
        self.camera_name = self.lineedit_name.text()
        self.camera_name_updated.emit(self._get_dev_str(), self.camera_name)

    def _cycle_flip(self):
        self.flip = (self.flip + 1) % len(video_transforms)
        self._update_ui()

    def _select_format(self, idx):
        self.format = self.available_formats[idx]
        self._refresh_quality()

    def _select_quality(self, idx):
        self.quality = self.modes[self.format][idx]

    def _refresh_quality(self):
        self.combo_quality.clear()
        for (w, h, f) in self.modes[self.format]:
            self.combo_quality.addItem('{}x{} {}'.format(w, h, f))

    def _toggle_capture(self):
        self.capture_on = not self.capture_on
        if not self.is_recording() and not self.is_streaming():
            self.capture_on = False

        if not self.capture_on:
            self.close_viewer.emit()

        self._update_ui()

        self._set_camera_status()

    def _set_camera_status(self):
        is_streaming = self.is_streaming()
        is_recording = self.is_recording()

        def worker():
            try:
                if self.capture_on:
                    fmt = self.format
                    width, height, fps = self.quality
                    self.server.set_camera_status(
                        dev_name=self.dev_name,
                        is_recording=is_recording,
                        is_streaming=is_streaming,
                        fmt=fmt,
                        width=width,
                        height=height,
                        framerate=fps,
                        host=self.host,
                        port=self.port
                    )
                    if is_streaming:
                        self._open_window()
                else:
                    self.server.set_camera_status(
                        dev_name=self.dev_name,
                        is_recording=False,
                        is_streaming=False
                    )
            except Exception as e:
                print(e)

        threading.Thread(target=worker).run()

    def _close_window(self):
        try:
            self.close_viewer.emit()
        except:
            pass

        self.viewer = None

    def _open_window(self):
        port = self.port
        pixel_format = self.format
        
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

        self.viewer = CommandRunner(cmd)
        self.viewer_thread = QThread()
        self.viewer.moveToThread(self.viewer_thread)
        self.viewer.finished.connect(self._force_stop_capture)
        self.close_viewer.connect(self.viewer.close)
        self.viewer_thread.started.connect(self.viewer.run)
        self.viewer_thread.start()

    def _force_stop_capture(self):
        if self.viewer is not None:
            self.viewer = None
        if self.viewer_thread is not None:
            self.viewer_thread.wait()
            self.viewer_thread = None

        self.capture_on = False
        self._update_ui()
        self._set_camera_status()

    def _apply_server_update(self):
        server_status = self.server.get_status()
        if self.dev_name not in server_status:
            return

        status = server_status[self.dev_name]


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


class DeviceLoader(QObject):
    finished = pyqtSignal(list)

    def __init__(self, servers, parent=None):
        super().__init__(parent)
        self.servers = servers

    @pyqtSlot()
    def load_devices(self):
        all_devices = []

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

        self.finished.emit(all_devices)


class StreamingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.camera_servers = []
        try:
            devices = DeviceServer().devices()
            for dev in devices:
                if dev.dev_type == DeviceType.camera_server:
                    self.camera_servers.append(dev.interface())
                    print('[streaming] detected camera server "{}"'.format(dev.name))
        except Exception as e:
            print(e)

        self.settings = Settings('streaming_widget')

        self.hostname = self.settings.get('hostname', '127.0.0.1')

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        settings_panel = SettingsPanel(self.hostname)
        settings_panel.updated_host.connect(self._update_host)
        main_layout.addWidget(settings_panel)

        self.camera_widgets_container = QWidget()
        self.camera_widgets_container.setLayout(QVBoxLayout())
        main_layout.addWidget(self.camera_widgets_container)

        main_layout.addStretch()


        self.loader = DeviceLoader(self.camera_servers)
        self.loader_thread = QThread()
        self.loader.moveToThread(self.loader_thread)
        self.loader.finished.connect(self._add_devices_from_list)
        self.loader_thread.started.connect(self.loader.load_devices)
        self.loader_thread.start()

    @pyqtSlot(list)
    def _add_devices_from_list(self, devices):
        for dev_name, modes, port, server in devices:
            try:
                server_name = server.get_name()
                self._add_device(dev_name, server_name, modes, self.hostname, port, server)
            except Exception as e:
                print(e)

    def _add_device(self, dev_name: str, server_name: str, modes, hostname: str, port: int, server):
        new_panel = CameraControl(dev_name, server_name, modes, hostname, port, server)
        new_panel.camera_name_updated.connect(self._update_camera_name)
        new_panel.load_data(self.settings.get('camera_names', {}))
        self.camera_widgets_container.layout().addWidget(new_panel)

    def _update_host(self, hostname: str):
        print('[streaming] hostname changed to {}'.format(hostname))

        self.settings.set('hostname', hostname)

        for cam in self.findChildren(CameraControl):
            cam.update_hostname(hostname)

    @pyqtSlot(str, str)
    def _update_camera_name(self, dev_str, camera_name):
        names = self.settings.get('camera_names', {})
        names[dev_str] = camera_name
        self.settings.set('camera_names', names)
