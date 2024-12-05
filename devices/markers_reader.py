import time
import socket
import subprocess
import threading
import posix_ipc

PROXY_PATH = 'devices/markers_proxy.py'
MARKER_LIFESPAN = 0.2
QUEUE_NAME = '/ar_markers'

class TagReader(object):
	def __init__(self, marker_lifespan=MARKER_LIFESPAN, proxy_path=PROXY_PATH):
		self._detected_markers = {}
		#self._proxy = subprocess.Popen(['source', '/opt/ros/kinetic/setup.bash', '&&', 'python2', proxy_path, QUEUE_NAME],
		#                               stdout=subprocess.PIPE, shell=True)
		self._queue = posix_ipc.MessageQueue(name=QUEUE_NAME, flags=posix_ipc.O_CREAT)
		self._worker = threading.Thread(target=self._read_markers, daemon=True)
		self._worker.start()
		self._data_lock = threading.Lock()

	def _read_markers(self):
		while True:
			msg, _ = self._queue.receive()
			line = msg.decode('ascii').strip()

			if len(line) == 0:
				continue

			id, x, y, z = line.split()
			with self._data_lock:
				self._detected_markers[id] = (time.time(), (x, y, z))

	def _filter_markers(self):
		timestamp_now = time.time()

		with self._data_lock:
			removed = []

			for id, (timestamp, _) in self._detected_markers.items():
				if timestamp_now - timestamp > MARKER_LIFESPAN:
					removed.append(id)

			for id in removed:
				self._detected_markers.pop(id)

	def get_markers(self):
			self._filter_markers()
			return [(id, position) for id, (_, position) in self._detected_markers.items()]
