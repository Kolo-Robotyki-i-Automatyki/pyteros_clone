from PyQt5 import QtWidgets, QtGui, QtCore

from devices.zeromq_device import DeviceWorker, DeviceInterface, remote, include_remote_methods

import os
import re
import socket
import subprocess
import threading
import time


DEFAULT_REQ_PORT = 13210
DEFAULT_PUB_PORT = 13211

VIDEO_FILES_DIR = os.path.expanduser('~/pyteros_vid')
VIDEO_LEN_NS = 300_000_000_000

RE_INDEX = re.compile(r"\s*Index\s*:\s([0-9]+)\s*")
RE_TYPE = re.compile(r"\s*Type\s*:\s*(.*)\s*")
RE_PIXEL_FORMAT = re.compile(r"\s*Pixel Format\s*:\s*'([^']*)'.*")
RE_NAME = re.compile(r"\s*Name\s*:\s*(.*)\s*")
RE_SIZE = re.compile(r"\s*Size[^0-9]*([0-9]+)x([0-9]+)\s*")
RE_INTERVAL = re.compile(r"\s*Interval[^(]*\(([0-9]+\.[0-9]+)\s*fps\)\s*")


def warn(fmt_str, *args):
	print('[camera] ' + fmt_str, *args)


class CaptureStatus:
	def __init__(self, is_recording: bool = False, is_streaming: bool = False,
			fmt: str = 'YUYV', width: int = 320, height: int = 240,
			framerate: str = '15/1', host: str = '127.0.0.1',
			port: int = 15999, capture_process = None):
		self.is_recording = is_recording
		self.is_streaming = is_streaming
		self.fmt = fmt
		self.width = width
		self.height = height
		self.framerate = framerate
		self.host = host
		self.port = port
		self.capture_process = capture_process


class CameraServerWorker(DeviceWorker):
	def __init__(self, req_port=DEFAULT_REQ_PORT, pub_port=DEFAULT_PUB_PORT, **kwargs):
		super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

		self.devices = {}

	def init_device(self):
		if not os.path.exists(VIDEO_FILES_DIR):
		    os.makedirs(VIDEO_FILES_DIR)

		self.lock = threading.Lock()
		self._discover_devices()

		subprocess.run(['pkill', '"gst-launch"'], shell=True)

	def status(self):
		with self.lock:
			return self._status()

	@remote
	def get_name(self):
		return socket.gethostname()

	@remote
	def get_devices(self):
		with self.lock:
			return list(self.devices.keys())

	@remote
	def get_modes(self, dev_name: str):
		with self.lock:
			return self.devices[dev_name]['modes'] if dev_name in self.devices else []

	@remote
	def get_saved_files(self):
		return os.listdir(VIDEO_FILES_DIR)

	@remote
	def set_camera_status(self, dev_name: str, is_recording: bool, is_streaming: bool,
			fmt: str = '', width: int = 0, height: int = 0, framerate: str = '',
			host: str = '', port: int = 0):
		with self.lock:
			self._stop_capture(dev_name)

			self.devices[dev_name]['status'].is_recording = is_recording
			self.devices[dev_name]['status'].is_streaming = is_streaming
			self.devices[dev_name]['status'].fmt = fmt
			self.devices[dev_name]['status'].width = width
			self.devices[dev_name]['status'].height = height
			self.devices[dev_name]['status'].framerate = framerate
			self.devices[dev_name]['status'].host = host
			self.devices[dev_name]['status'].port = port

			if is_recording or is_streaming:
				self._start_capture(dev_name)

	def _status(self):
		status = {}

		for dev_name in self.devices:
			ds = self.devices[dev_name]['status']

			if ds.is_recording or ds.is_streaming:
				if ds.capture_process.returncode is not None:
					self.devices[dev_name]['status'].is_recording = False
					self.devices[dev_name]['status'].is_streaming = False
					ds = self.devices[dev_name]['status']

			status[dev_name] = {
				'is_recording': ds.is_recording,
				'is_streaming': ds.is_streaming,
				'fmt': ds.fmt,
				'width': ds.width,
				'height': ds.height,
				'framerate': ds.framerate,
				'host': ds.host,
				'port': ds.port,
			}

		return status

	def _stop_capture(self, dev_name: str):
		try:
			self.devices[dev_name]['status'].capture_process.kill()
			self.devices[dev_name]['status'].capture_process = None
		except Exception as e:
			print(e)

	def _start_capture(self, dev_name: str):
		status = self.devices[dev_name]['status']

		if status.fmt == 'H264' and status.is_recording:
			warn('recording a h264 stream is not implemented')
			self.devices[dev_name]['status'].is_recording = False
			status.is_recording = False

		if not status.is_recording and not status.is_streaming:
			return

		filename = '{:010}_{}_%02d.avi'.format(int(time.time()), dev_name.replace('/', '_'))
		str_path = os.path.join(VIDEO_FILES_DIR, filename)

		str_src = ''
		str_record = ''
		str_stream = ''

		if status.fmt == 'YUYV':
			str_src = 'gst-launch-1.0 -vvv v4l2src device={} ' \
				'! video/x-raw,format=YUY2,width={},height={},framerate={}' \
				.format(dev_name, status.width, status.height, status.framerate)
			str_record = 'splitmuxsink muxer=avimux location={} max-size-time={}' \
				.format(str_path, VIDEO_LEN_NS)
			str_stream = 'jpegenc ! rtpjpegpay ! udpsink host={} port={}' \
				.format(status.host, status.port)
		elif status.fmt == 'MJPG':
			str_src = 'gst-launch-1.0 -vvv v4l2src device={} ' \
				'! image/jpeg,width={},height={},framerate={}' \
				.format(dev_name, status.width, status.height, status.framerate)
			str_record = 'splitmuxsink muxer=avimux location={} max-size-time={}' \
				.format(str_path, VIDEO_LEN_NS)
			str_stream = 'rtpjpegpay ! udpsink host={} port={}' \
				.format(status.host, status.port)
		elif status.fmt == 'H264':
			str_src = 'gst-launch-1.0 -vvv v4l2src device={} ' \
				'! video/x-h264,width={},height={},framerate={}' \
				.format(dev_name, status.width, status.height, status.framerate)
			str_stream = 'rtph264pay ! udpsink host={} port={}' \
				.format(status.host, status.port)
		else:
			warn('unrecognized format "{}"'.format(status.fmt))
			return

		str_cmd = ''
		if status.is_streaming and status.is_recording:
			str_cmd = '{} ! tee name=t ! queue ! {} t. ! queue ! {}' \
				.format(str_src, str_record, str_stream)
		elif status.is_recording:
			str_cmd = '{} ! {}'.format(str_src, str_record)
		elif status.is_streaming:
			str_cmd = '{} ! {}'.format(str_src, str_stream)

		warn(str_cmd)

		capture_process = subprocess.Popen(str_cmd.split(), shell=False)
		self.devices[dev_name]['status'].capture_process = capture_process

	def _discover_devices(self):
		devices = []
	
		list_devices_process = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE, shell=True)
		for line in list_devices_process.stdout.decode('utf-8').split('\n'):
			if len(line.strip()) == 0:
				continue
			if line[0].isspace():
				devices.append(line.strip())

		for dev_name in devices:
			all_formats = []

			cmd = ['v4l2-ctl', '--list-formats-ext', '-d', dev_name]
			list_formats_process = subprocess.run(cmd, stdout=subprocess.PIPE)

			lines = list_formats_process.stdout.decode('utf-8').split('\n')
			lines = [line.strip() for line in lines if len(line.strip()) > 0]

			i = 0
			while i < len(lines):
				for fmt in ['YUYV', 'MJPG', 'H264']:
					if fmt in lines[i]:
						pixel_format = fmt
						i += 1
						break
				else:
					i += 1
					continue

				while i < len(lines) and RE_SIZE.match(lines[i]) is None:
					i += 1

				while i < len(lines):
					size_match = RE_SIZE.match(lines[i])
					if size_match is None:
						break

					width, height = (int(x) for x in size_match.groups())
					i += 1

					max_fps = 0.0

					while i < len(lines):
						interval_match = RE_INTERVAL.match(lines[i])
						if interval_match is None:
							break

						fps = float(interval_match.groups()[0])
						i += 1

						if fps > max_fps:
							max_fps = fps

					if max_fps == 0.0:
						continue

					fps_str = ''
					for divisor in [1, 2, 3, 4]:
						multiplied = max_fps * divisor
						if abs(round(multiplied) - multiplied) <= 0.05:
							fps_str = '{}/{}'.format(int(multiplied), divisor)
							break
					else:
						continue

					all_formats.append((pixel_format, width, height, fps_str))

			if len(all_formats) > 0:
				with self.lock:
					self.devices[dev_name] = {
						'modes': all_formats,
						'status': CaptureStatus(),
					}


@include_remote_methods(CameraServerWorker)
class CameraServer(DeviceInterface):
	def __init__(self, req_port=DEFAULT_REQ_PORT, pub_port=DEFAULT_PUB_PORT, **kwargs):
		super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
		
		self.lock = threading.Lock()
		self.last_status = {}
		self.status_callback = None

	def createDock(self, parentWidget, menu=None):
		pass
