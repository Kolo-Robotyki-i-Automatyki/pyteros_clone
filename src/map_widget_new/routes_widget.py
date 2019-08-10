from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from src.common.coord import *


class Routes(QGroupBox):
	auto_started = pyqtSignal(list)
	auto_stopped = pyqtSignal()
	route_selected = pyqtSignal(list)
	pos_selected = pyqtSignal(float, float)

	def __init__(self, parent=None):
		super().__init__('Routes', parent)

		self.routes = {}

		self.selected_route = None
		self.selected_node = -1


		self.label_autonomy = QLabel('')
		button_stop = QPushButton('Start')
		button_start = QPushButton('Stop')
		self.list_routes = QListWidget()
		button_new = QPushButton('New')
		button_delete = QPushButton('Delete')
		self.list_nodes = QListWidget()
		self.lineedit_latitude = QLineEdit()
		self.lineedit_longitude = QLineEdit()
		button_add = QPushButton('Add')
		button_remove = QPushButton('Remove')

		button_stop.clicked.connect(self._stop_auto)
		button_start.clicked.connect(self._start_auto)
		self.list_routes.itemClicked.connect(self._select_route)
		button_new.clicked.connect(self._new_route)
		button_delete.clicked.connect(self._delete_route)
		self.list_nodes.currentRowChanged.connect(self._select_node_idx)
		button_add.clicked.connect(self._add_node)
		button_remove.clicked.connect(self._remove_node)

		main_layout = QFormLayout()
		self.setLayout(main_layout)

		main_layout.addRow(self.label_autonomy)
		main_layout.addRow(button_stop, button_start)
		main_layout.addRow(self.list_routes)
		main_layout.addRow(button_new, button_delete)
		main_layout.addRow(self.list_nodes)
		main_layout.addRow(QLabel('Latitude'), self.lineedit_latitude)
		main_layout.addRow(QLabel('Longitude'), self.lineedit_longitude)
		main_layout.addRow(button_add, button_remove)


	def load_data(self, data):
		self.routes.update(data)
		self._refresh_routes()
		self._refresh_nodes()

	def get_data(self):
		return self.routes

	@pyqtSlot(str)
	def display_auto_status(self, status):
		self.label_autonomy.setText(status)

	@pyqtSlot(float, float)
	def select_pos(self, lat, lon):
		self.lineedit_latitude.setPlaceholderText('{:2.9f}'.format(lat))
		self.lineedit_longitude.setPlaceholderText('{:2.9f}'.format(lon))

	def _stop_auto(self):
		pass

	def _start_auto(self):
		pass

	def _select_route(self, item):
		route_name = str(item.text())
		if route_name not in self.routes.keys():
			print('[map] route "{}" not found!'.format(route_name))
			return
		self.selected_route = route_name
		self.route_selected.emit(self.routes[route_name])
		self._refresh_nodes()

	@pyqtSlot()
	def _new_route(self):
		name_unicode, success = QInputDialog.getText(None, "New route","Name:", QLineEdit.Normal, "")
		name = name_unicode
		if success and len(name) > 0 and name not in self.routes:
			self.routes[name] = []

		self._refresh_routes()

	pyqtSlot()
	def _delete_route(self):
		if self.selected_route is None:
			return
		if self.selected_route not in self.routes.keys():
			print('[map] route "{}" not found!'.format(self.selected_route))
			return

		del self.routes[self.selected_route]
		self._refresh_routes()

		self.selected_route = None
		self.route_selected.emit([])

	@pyqtSlot(int)
	def _select_node_idx(self, idx):
		self.selected_node = idx

		try:
			route = self.routes[self.selected_route]
			lat, lon = route[idx]
			self.pos_selected.emit(lat, lon)
		except:
			pass

	@pyqtSlot()
	def _add_node(self):
		if self.selected_route not in self.routes.keys():
			return

		lat = get_coord_from_lineedit(self.lineedit_latitude, True)
		lon = get_coord_from_lineedit(self.lineedit_longitude, False)

		if self.selected_node >= 0 and self.selected_node < len(self.routes[self.selected_route]):
			self.routes[self.selected_route].insert(self.selected_node, (lat, lon))
		else:
			self.routes[self.selected_route].append((lat, lon))

		self._refresh_nodes();

		self.route_selected.emit(self.routes[self.selected_route])

	@pyqtSlot()
	def _remove_node(self):
		try:
			route = self.routes[self.selected_route]
			node_idx = self.selected_node
			if node_idx >= 0 and node_idx < len(route):
				self.routes[self.selected_route].pop(node_idx)
			self._refresh_nodes()
		except:
			pass

	def _refresh_routes(self):
		self.list_routes.clear()
		for route_name in sorted(self.routes.keys()):
			self.list_routes.addItem(route_name)

	def _refresh_nodes(self):
		self.list_nodes.clear()

		try:
			route = self.routes[self.selected_route]
			for (lat, lon) in route:
				self.list_nodes.addItem('{:2.8f}° {:2.8f}°'.format(lat, lon))
		except:
			pass

		if self.selected_route in self.routes.keys():
			self.route_selected.emit(self.routes[self.selected_route])
