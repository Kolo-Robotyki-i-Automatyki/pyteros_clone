from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from src.map_widget_new.canvas_widget import Canvas
from src.map_widget_new.routes_widget import Routes
from src.map_widget_new.photo_loader_widget import PhotoLoader
from src.map_widget_new.pins_widget import Pins

from devices.rover import Rover
from src.common.settings import Settings

import math


class MapWidget(QWidget):
	rover_updated = pyqtSignal(object, float)
	autonomy_updated = pyqtSignal(str)

	def __init__(self, active_devices, parent=None):
		super().__init__(parent)

		self.rover = None
		for name, dev in active_devices.items():
			if isinstance(dev, Rover):
				self.rover = dev
				break
		else:
			print('[map] rover not connected')

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
		self.autonomy_updated.connect(self.routes.display_auto_status)

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

		self.update_timer = QTimer()
		self.update_timer.setSingleShot(False)
		self.update_timer.setInterval(100)
		self.update_timer.timeout.connect(self._update_status)
		self.update_timer.start()

	def _save_config(self):
		self.config.set('routes', self.routes.get_data(), save=False)
		self.config.set('pins', self.pins.get_data(), save=False)
		self.config.set('photos', self.photo_loader.get_data(), save=False)
		self.config.save()
		print('[map] autosave')

	def _update_status(self):
		if self.rover is None:
			return

		status = self.rover.get_last_status()
		lat, lon = status.get('coordinates', (0, 0))
		heading = math.degrees(status.get('heading', 0))
		self.rover_updated.emit((lat, lon), heading)

		auto_status = status.get('autonomy', '')
		self.autonomy_updated.emit(auto_status)

	def _start_auto(self, route):
		if self.rover is not None:
			self.rover.set_waypoints(route)
			self.rover.start_auto_from_waypoint(0)

	def _stop_auto(self):
		if self.rover is None:
			self.rover.end_auto()
