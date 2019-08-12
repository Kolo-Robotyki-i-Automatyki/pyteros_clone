from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import os


class PhotoLoader(QGroupBox):
	maps_loaded = pyqtSignal(list)

	def __init__(self, parent=None):
		super().__init__('Maps', parent)

		self.loaded_maps = {}

		self.lineedit_path = QLineEdit()
		button_open = QPushButton('Open')

		button_open.clicked.connect(self._load_maps)

		main_layout = QFormLayout()
		self.setLayout(main_layout)

		main_layout.addRow(self.lineedit_path, button_open)


	def load_data(self, data):
		if 'path' in data:
			self.lineedit_path.setText(data['path'])

	def get_data(self):
		path = self.lineedit_path.text()
		return {'path': path}


	@pyqtSlot()
	def _load_maps(self):
		directory = self.lineedit_path.text()
		if len(directory) == 0:
			return
		path = os.path.expanduser(directory)
		if not os.path.isdir(path):
			return

		self._load_directory(path)

		if len(self.loaded_maps) > 0:
			print('[map] loaded {} map files in total'.format(len(self.loaded_maps)))
			maps_list = [val for _, val in self.loaded_maps.items()]
			self.maps_loaded.emit(maps_list)

	def _load_directory(self, path):
		try:
			files = os.listdir(path)
			world_files = [ f for f in files if f.endswith('.pgw') ]

			for filename in world_files:
				self._process_single_world_file(path, filename)
		except Exception as e:
			print(e)

	def _process_single_world_file(self, path, world_file):
		if world_file in self.loaded_maps.keys():
			return

		world_file_full = os.path.join(path, world_file)

		with open(world_file_full, 'r') as map_metadata:
			lines = map_metadata.readlines()

			x_pixel_size = float(lines[0])
			y_pixel_size = float(lines[3])
			longitude    = float(lines[4])
			latitude     = float(lines[5])

		image_filename = world_file_full.replace('.pgw', '.png')
		image = QImage(image_filename)
		width, height = image.size().width(), image.size().height()

		top_left     = (latitude, longitude)
		bottom_right = (latitude + y_pixel_size * height, longitude + x_pixel_size * width)

		self.loaded_maps[world_file] = (image, (top_left, bottom_right))
