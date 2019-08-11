from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from devices.autonomy import Task
from src.common.coord import *


class Routes(QGroupBox):
	auto_started = pyqtSignal(list)
	auto_stopped = pyqtSignal()
	route_selected = pyqtSignal(list)
	pos_selected = pyqtSignal(float, float)

	def __init__(self, parent=None):
		super().__init__('Routes', parent)

		self.routes = {}

		self.saved_pos = None
		self.saved_rover_pos = None

		self.selected_route = None
		self.selected_node = -1


		button_stop = QPushButton('Start')
		button_start = QPushButton('Stop')
		self.list_routes = QListWidget()
		button_new = QPushButton('New')
		button_delete = QPushButton('Delete')
		self.list_nodes = QListWidget()
		button_add_selected = QPushButton('Add selected point')
		button_add_current = QPushButton('Add rover posiiton')
		self.lineedit_script = QLineEdit('')
		button_add_script = QPushButton('Add script')
		button_remove = QPushButton('Remove')

		button_stop.clicked.connect(self._stop_auto)
		button_start.clicked.connect(self._start_auto)
		self.list_routes.itemClicked.connect(self._select_route)
		button_new.clicked.connect(self._new_route)
		button_delete.clicked.connect(self._delete_route)
		self.list_nodes.currentRowChanged.connect(self._select_node_idx)
		button_add_selected.clicked.connect(self._add_node_selected)
		button_add_current.clicked.connect(self._add_node_current)
		button_add_script.clicked.connect(self._add_node_script)
		button_remove.clicked.connect(self._remove_node)

		main_layout = QFormLayout()
		self.setLayout(main_layout)

		main_layout.addRow(button_stop, button_start)
		main_layout.addRow(self.list_routes)
		main_layout.addRow(button_new, button_delete)
		main_layout.addRow(self.list_nodes)
		main_layout.addRow(button_add_selected, button_add_current)
		main_layout.addRow(self.lineedit_script, button_add_script)
		main_layout.addRow(button_remove)


	def load_data(self, data):
		self.routes.update(data)
		self._refresh_routes()
		self._refresh_nodes()

	def get_data(self):
		return self.routes

	@pyqtSlot(float, float)
	def select_pos(self, lat, lon):
		self.saved_pos = (lat, lon)

	@pyqtSlot(object, float)
	def set_rover_coord(self, pos, heading):
		self.saved_rover_pos = pos

	def _start_auto(self):
		try:
			route = self.routes[self.selected_route]
			self.auto_started.emit(route)
		except Exception as e:
			print(e)

	def _stop_auto(self):
		self.auto_stopped.emit()

	def _select_route(self, item):
		route_name = str(item.text())
		if route_name not in self.routes.keys():
			print('[map] route "{}" not found!'.format(route_name))
			return
		self.selected_route = route_name
		self._publish_route()
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

	def _add_node(self, task):
		if self.selected_node >= 0 and self.selected_node < len(self.routes[self.selected_route]):
			self.routes[self.selected_route].insert(self.selected_node, task)
		else:
			self.routes[self.selected_route].append(task)

		print('adding {}'.format(task))

		self._refresh_nodes();

		self._publish_route()

	@pyqtSlot()
	def _add_node_selected(self):
		if self.selected_route not in self.routes.keys():
			return
		if self.saved_pos is None:
			return

		task = (Task.DRIVE_TO, self.saved_pos)
		self._add_node(task)

	@pyqtSlot()
	def _add_node_current(self):
		if self.selected_route not in self.routes.keys():
			return
		if self.saved_rover_pos is None:
			return

		task = (Task.DRIVE_TO, self.saved_rover_pos)
		self._add_node(task)

	@pyqtSlot()
	def _add_node_script(self):
		script_name = self.lineedit_script.text()
		if len(script_name) == 0:
			return

		task = (Task.RUN_SCRIPT, (script_name,))
		self._add_node(task)

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
			for task_type, args in route:
				if task_type == Task.DRIVE_TO:
					lat, lon = args
					text = 'DROVE TO ({:2.8f}°, {:2.8f}°)'.format(lat, lon)
				elif task_type == Task.RUN_SCRIPT:
					script_name, = args
					text = 'RUN "{}"'.format(script_name)
				else:
					print('[map/routes] invalid task type "{}"'.format(task_type))
				self.list_nodes.addItem(text)
		except Exception as e:
			print(e)

		self._publish_route()

	def _publish_route(self):
		try:
			route = self.routes[self.selected_route]
			waypoints = [args for (task_type, args) in route if task_type == Task.DRIVE_TO]
			self.route_selected.emit(waypoints)
		except Exception as e:
			print(e)
