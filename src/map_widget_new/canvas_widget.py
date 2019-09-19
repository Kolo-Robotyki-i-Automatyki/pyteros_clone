from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from src.common.coord import *

import math
import time


TRACE_RESOLUTION = 1.0


# an arrow representing the rover
arrow_shape = QPolygonF([
	QPointF(  0, -14),
	QPointF(-12,  14),
	QPointF(  0,   6),
	QPointF( 12,  14)]
)


class Canvas(QWidget):
	pos_selected = pyqtSignal(float, float)

	def __init__(self, parent=None):
		super().__init__(parent)

		self.map_scaling = 0.5 # meters per pixel
		self.pos = (0, 0) # latitude, longitude
		
		self.dragging = False
		self.prev_click = (0, 0)

		self.images = []
		self.route = []
		self.pins = []
		self.selected_point = None
		self.rover_pos = None
		self.rover_heading = 0
		self.rover_trace = []
		self.auto_status = {}

		self.lineedit_latitude = QLineEdit()
		self.lineedit_longitude = QLineEdit()
		self.checkbox_follow = QCheckBox('Follow the rover')
		
		self.lineedit_latitude.setPlaceholderText('latitude')
		self.lineedit_longitude.setPlaceholderText('longitude')
		self.checkbox_follow.setChecked(True)

		self.lineedit_latitude.editingFinished.connect(self._publish_pos)
		self.lineedit_longitude.editingFinished.connect(self._publish_pos)

		main_layout = QVBoxLayout()
		self.setLayout(main_layout)
		main_layout.addStretch()
		main_layout.addWidget(self.checkbox_follow)
		main_layout.addWidget(self.lineedit_latitude)
		main_layout.addWidget(self.lineedit_longitude)

		self.repaint_timer = QTimer()
		self.repaint_timer.setSingleShot(False)
		self.repaint_timer.setInterval(0.05)
		self.repaint_timer.timeout.connect(self.repaint)
		self.repaint_timer.start()

	@pyqtSlot(object, float)
	def set_rover_coord(self, pos, heading):
		self.rover_pos = pos
		self.rover_heading = heading

		if len(self.rover_trace) == 0:
			self.rover_trace.append(self.rover_pos)
		else:
			prev_pos = self.rover_trace[-1]
			dx, dy = relative_xy(prev_pos, pos)
			if math.sqrt(dx * dx + dy * dy) >= TRACE_RESOLUTION:
				self.rover_trace.append(self.rover_pos)

	@pyqtSlot(list)
	def show_images(self, images):
		self.images.extend(images)

	@pyqtSlot(list)
	def display_route(self, route):
		self.route = route

	@pyqtSlot(list)
	def display_pins(self, pins):
		self.pins = pins

	@pyqtSlot(dict)
	def display_auto_status(self, status):
		self.auto_status = status

	@pyqtSlot(float, float)
	def select_pos(self, lat, lon):
		self.selected_point = (lat, lon)
		self.lineedit_latitude.setText('{:2.9f}'.format(lat))
		self.lineedit_longitude.setText('{:2.9f}'.format(lon))


	def paintEvent(self, event):
		if self.checkbox_follow.isChecked() and self.rover_pos is not None:
			self.pos = self.rover_pos

		painter = QPainter(self)

		canvas_width, canvas_height = self.width(), self.height()

		# background
		painter.fillRect(0, 0, canvas_width, canvas_height, QBrush(QColor.fromRgb(236, 232, 228)))

		# map
		for image, ((top, left), (bottom, right)) in self.images:
			left, top     = self._pos_to_xy((top, left))
			right, bottom = self._pos_to_xy((bottom, right))

			if left > canvas_width or right < 0 or top > canvas_height or bottom < 0:
				continue

			img_rect = QRect(left, top, math.ceil(right - left), math.ceil(bottom - top))
			painter.drawImage(img_rect, image)

		# trace
		painter.setPen(QPen(QColor.fromRgb(125, 190, 255), 3))
		if len(self.rover_trace) > 0:
			trace_xy = [self._pos_to_xy(pos) for pos in self.rover_trace]
			trace_xy.append(self._pos_to_xy(self.rover_pos))
			for (a, b) in zip(trace_xy[:-1], trace_xy[1:]):
				painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))

		# routes
		route_xy = [self._pos_to_xy(node) for node in self.route]
		if len(route_xy) >= 1:
			painter.setPen(QPen(QColor.fromRgb(70, 255, 160), 4))
			for (a, b) in zip(route_xy[:-1], route_xy[1:]):
				painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
			painter.setPen(QPen(QColor.fromRgb(108, 137, 153), 3))
			for x, y in route_xy:
				painter.drawEllipse(QPointF(x, y), 3.0, 3.0)

		# pins
		for pos, description in self.pins:
			x, y = self._pos_to_xy(pos)
			painter.setPen(QPen(QColor.fromRgb(250, 208, 208), 2))
			painter.setBrush(QBrush(QColor.fromRgb(208, 36, 36)))
			painter.drawEllipse(QPointF(x, y), 5.0, 5.0)

			font = QFont("Arial", 12, QFont.Normal)
			font.setFixedPitch(True)
			painter.setFont(font)

			painter.setPen(Qt.white)
			painter.drawText(QPointF(x + 9,  y + 5), description)
			painter.drawText(QPointF(x + 9,  y + 7), description)
			painter.drawText(QPointF(x + 8,  y + 6), description)
			painter.drawText(QPointF(x + 10, y + 6), description)

			painter.setPen(Qt.black)
			painter.drawText(QPointF(x + 9, y + 6), description)

		# mouse click
		if self.selected_point is not None:
			x, y = self._pos_to_xy(self.selected_point)
			painter.setPen(QPen(Qt.red, 3))
			painter.setBrush(QBrush(Qt.white))
			painter.drawEllipse(QPoint(x, y), 4.0, 4.0)

		# position and heading
		painter.setPen(Qt.black)
		if self.rover_pos is None:
			painter.drawText(QPointF(5, 15), 'latitude:  \tunknown')
			painter.drawText(QPointF(5, 30), 'longitude: \tunknown')
		else:
			lat, lon = self.rover_pos
			painter.drawText(QPointF(5, 15), 'latitude: \t{:.6f}'.format(lat))
			painter.drawText(QPointF(5, 30), 'longitude:\t{:.6f}'.format(lon))
		painter.drawText(QPointF(5, 45), 'heading:  \t{:.1f}'.format(self.rover_heading))

		# autonomy status
		try:
			painter.setPen(Qt.black)
			status = self.auto_status
			rows = []
			if 'state' in status.keys():
				rows.append('Autonomy state: {}'.format(status['state']))
			if 'next_task' in status.keys():
				rows.append('Next task: {}'.format(status['next_task']))
			if 'tasks' in status.keys():
				rows.append('Tasks:')
				for task_descr in status['tasks']:
					rows.append('\t{}'.format(task_descr))
			for key, value in status.items():
				if key in ['state', 'next_task', 'tasks']:
					continue
				rows.append('{} := {}'.format(key, value))
			next_row_pos = 70
			for row in rows:
				painter.drawText(QPointF(5, next_row_pos), row)
				next_row_pos += 15
		except Exception as e:
			print('[map/canvas] drawing autonomy status: {}'.format(e))

		# rover
		if self.rover_pos is not None:
			painter.save()
			painter.setPen(QPen(Qt.white, 1))
			painter.setBrush(QBrush(QColor.fromRgb(0, 128, 255)))
			x, y = self._pos_to_xy(self.rover_pos)
			painter.translate(x, y)
			painter.rotate(self.rover_heading)
			painter.drawPolygon(arrow_shape)
			painter.restore()

	def wheelEvent(self, event):
		y_shift = event.angleDelta().y()
		# TODO nice scrolling
		factor = 1.1 if y_shift <= 0 else 0.9
		self.map_scaling *= factor

	def mousePressEvent(self, event):
		click_xy = (event.x(), event.y())

		if event.button() == Qt.LeftButton:
			click_pos = self._xy_to_pos(click_xy)
			self.pos_selected.emit(*click_pos)
			self.select_pos(*click_pos)
		elif event.button() == Qt.RightButton:
			self.dragging = True
			self.prev_click = click_xy
		else:
			print('unknown mouse button!')

	def mouseMoveEvent(self, event):
		if not self.dragging:
			return

		w, h = self.width(), self.height()
		click_xy = (event.x(), event.y())
		px, py = self.prev_click
		self.prev_click = (event.x(), event.y())
		dx = event.x() - px
		dy = event.y() - py
		self.pos = self._xy_to_pos((w / 2 - dx, h / 2 - dy))

	def mouseReleaseEvent(self, event):
		if event.button() == Qt.RightButton:
			self.dragging = False

	pyqtSlot()
	def _publish_pos(self):
		lat = get_coord_from_lineedit(self.lineedit_latitude, is_latitude=True)
		lon = get_coord_from_lineedit(self.lineedit_longitude, is_latitude=False)

		self.pos_selected.emit(lat, lon)

	def _xy_to_pos(self, xy):
		x, y = xy
		w, h = self.width(), self.height()
		dx = self.map_scaling * (x - w / 2)
		dy = self.map_scaling * (h / 2 - y)
		return move(self.pos, (dx, dy))

	def _pos_to_xy(self, pos):
		lat, lon = pos
		w, h = self.width(), self.height()
		rel_x, rel_y = relative_xy(self.pos, pos)
		dx = rel_x / self.map_scaling
		dy = rel_y / self.map_scaling
		return (w / 2 + dx, h / 2 - dy)
