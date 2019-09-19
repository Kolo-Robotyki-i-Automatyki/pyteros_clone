from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from src.map_widget_new.canvas_widget import Canvas
from src.map_widget_new.routes_widget import Routes
from src.map_widget_new.photo_loader_widget import PhotoLoader
from src.map_widget_new.pins_widget import Pins

from DeviceServerHeadless import DeviceType
from devices.rover import Rover
from src.common.misc import *
from src.common.settings import Settings

import math
import threading
import time
import traceback


RECONNECT_PERIOD_S = 1.0


class MapWidget(QWidget):
	rover_updated = pyqtSignal(object, float)
	autonomy_updated = pyqtSignal(dict)

	def __init__(self, device_server, parent=None):
		super().__init__(parent)

		self.lock = threading.Lock()

		self.device_server = device_server

		self.rover = None
		self.autonomy = None

		self.config = Settings('map_widget')

		self.routes = Routes()
		self.pins = Pins()
		self.photo_loader = PhotoLoader()
		self.canvas = Canvas()

		self.routes.pos_selected.connect(self.canvas.select_pos)
		self.pins.pos_selected.connect(self.canvas.select_pos)
		self.canvas.pos_selected.connect(self.routes.select_pos)
		self.canvas.pos_selected.connect(self.pins.select_pos)
		self.routes.route_selected.connect(self.canvas.display_route)
		self.pins.pins_updated.connect(self.canvas.display_pins)
		self.photo_loader.maps_loaded.connect(self.canvas.show_images)
		self.routes.auto_started.connect(self._start_auto)
		self.routes.auto_stopped.connect(self._stop_auto)
		self.rover_updated.connect(self.canvas.set_rover_coord)
		self.rover_updated.connect(self.routes.set_rover_coord)
		self.autonomy_updated.connect(self.canvas.display_auto_status)

		self.routes.load_data(self.config.get('routes', {}))
		self.pins.load_data(self.config.get('pins', {}))
		self.photo_loader.load_data(self.config.get('photos', {}))

		side = QWidget()
		side.setLayout(QVBoxLayout())
		side.layout().addWidget(self.routes)
		side.layout().addWidget(self.pins)
		side.layout().addWidget(self.photo_loader)
		side.layout().addStretch()

		main_layout = QHBoxLayout()
		self.setLayout(main_layout)		
		main_layout.addWidget(side, stretch=0)
		main_layout.addWidget(self.canvas, stretch=1)

		self.save_timer = QTimer()
		self.save_timer.setSingleShot(False)
		self.save_timer.setInterval(15000)
		self.save_timer.timeout.connect(self._save_config)
		self.save_timer.start()

		self.new_rover_status = None
		self.new_autonomy_status = None

		threading.Thread(target=self._discover_devices, daemon=True).start()

		self.update_timer = QTimer()
		self.update_timer.setSingleShot(False)
		self.update_timer.setInterval(100)
		self.update_timer.timeout.connect(self._update_status)
		self.update_timer.start()

	def _discover_devices(self):
		while True:
			try:
				with self.lock:
					if self.rover is None:
						rover = self.device_server.find_device([DeviceType.rover, DeviceType.fake_rover])
						if rover is not None:
							self.rover = rover
							self.rover.create_listener_thread(self._process_rover_status)

					if self.autonomy is None:
						autonomy = self.device_server.find_device([DeviceType.autonomy])
						if autonomy is not None:
							self.autonomy = autonomy
							self.autonomy.create_listener_thread(self._process_autonomy_status)

			except:
				traceback.print_exc()

			time.sleep(RECONNECT_PERIOD_S)

	def _process_rover_status(self, rover_status):
		self.new_rover_status = rover_status

	def _process_autonomy_status(self, autonomy_status):
		self.new_autonomy_status = autonomy_status

	def _save_config(self):
		self.config.set('routes', self.routes.get_data(), save=False)
		self.config.set('pins', self.pins.get_data(), save=False)
		self.config.set('photos', self.photo_loader.get_data(), save=False)
		self.config.save()

	def _update_status(self):
		try:
			with self.lock:
				if self.new_rover_status is not None:
					lat, lon = self.new_rover_status['coordinates']
					heading = math.degrees(self.new_rover_status['heading'])
					self.rover_updated.emit((lat, lon), heading)
					self.new_rover_status = None
		except:
			print('[map] invalid rover status')
			traceback.print_exc()

		try:
			with self.lock:
				if self.new_autonomy_status is not None:
					self.autonomy_updated.emit(self.new_autonomy_status)
					self.new_autonomy_status = None
		except:
			print('[map] invalid autonomy status')
			traceback.print_exc()

	def _start_auto(self, route):
		if self.autonomy is not None:
			self.autonomy.set_tasks(route)
			self.autonomy.start_from_task(0)

	def _stop_auto(self):
		if self.autonomy is not None:
			self.autonomy.end()
