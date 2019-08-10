from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


class Pins(QGroupBox):
	pos_selected = pyqtSignal(float, float)
	pins_updated = pyqtSignal(list)

	def __init__(self, parent=None):
		super().__init__('Pins', parent)

		self.pins = []
		self.selected_pin = -1

		self.latitude = 0.0
		self.longitude = 0.0
		self.name = ''

		self.list_points = QListWidget()
		self.lineedit_name = QLineEdit()
		button_add = QPushButton('Add')
		button_remove = QPushButton('Remove')

		self.list_points.currentRowChanged.connect(self._select_pin_idx)
		self.lineedit_name.editingFinished.connect(self._set_name)
		button_add.clicked.connect(self._add_pin)
		button_remove.clicked.connect(self._remove_pin)

		main_layout = QFormLayout()
		self.setLayout(main_layout)

		main_layout.addRow(self.list_points)
		main_layout.addRow(QLabel('Name'), self.lineedit_name)
		main_layout.addRow(button_add, button_remove)


	def load_data(self, data):
		for key, val in data.items():
			self.pins.append(((val[0], val[1]), key))
		self._refresh_pins()
		self.pins_updated.emit(self.pins)

	def get_data(self):
		pins_dict = {name: [lat, lon] for ((lat, lon), name) in self.pins}
		return pins_dict


	@pyqtSlot(float, float)
	def select_pos(self, lat, lon):
		self.latitude = lat
		self.longitude = lon

	@pyqtSlot(int)
	def _select_pin_idx(self, idx):
		self.selected_pin = idx
		pos, _ = self.pins[idx]
		self.pos_selected.emit(*pos)

	@pyqtSlot()
	def _set_name(self):
		self.name = self.lineedit_name.text()

	@pyqtSlot()
	def _add_pin(self):
		if len(self.name) == 0:
			return

		self.pins.append(((self.latitude, self.longitude), self.name))
		self._refresh_pins()
		self.pins_updated.emit(self.pins)

	@pyqtSlot()
	def _remove_pin(self):
		idx = self.selected_pin
		if idx >= 0 and idx < len(self.pins):
			self.pins.pop(idx)
			self._refresh_pins()

	def _refresh_pins(self):
		self.list_points.clear()
		for _, name in self.pins:
			self.list_points.addItem(name)
