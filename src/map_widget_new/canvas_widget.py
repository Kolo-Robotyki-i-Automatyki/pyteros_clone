from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from src.common.coord import *


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
		self.rover_pos = (0, 0)
		self.rover_heading = 0

		self.repaint_timer = QTimer()
		self.repaint_timer.setSingleShot(False)
		self.repaint_timer.setInterval(0.05)
		self.repaint_timer.timeout.connect(self.repaint)
		self.repaint_timer.start()

	@pyqtSlot(object, float)
	def set_rover_coord(self, pos, heading):
		self.rover_pos = pos
		self.rover_heading = heading

	@pyqtSlot(list)
	def show_images(self, images):
		self.images.extend(images)

	@pyqtSlot(list)
	def display_route(self, route):
		self.route = route

	@pyqtSlot(list)
	def display_pins(self, pins):
		self.pins = pins

	@pyqtSlot(float, float)
	def select_pos(self, lat, lon):
		self.selected_point = (lat, lon)


	def paintEvent(self, event):
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

		# # trace
		# painter.setPen(QPen(QColor.fromRgb(125, 190, 255), 3))
		# if len(self.rover_trace) > 0:
		#     trace_xy = [self.__pos_to_xy(pos) for pos, _ in self.rover_trace]
		#     trace_xy.append(self.__pos_to_xy(self.rover_pos))
		#     for (a, b) in zip(trace_xy[:-1], trace_xy[1:]):
		#         painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))

		# routes
		route_xy = [self._pos_to_xy(node) for node in self.route]
		if len(route_xy) >= 2:
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
		painter.drawText(QPointF(5, 15), 'latitude: \t{:.6f}'.format(self.rover_pos[0]))
		painter.drawText(QPointF(5, 30), 'longitude:\t{:.6f}'.format(self.rover_pos[1]))
		painter.drawText(QPointF(5, 45), 'heading:  \t{:.1f}'.format(self.rover_heading))

		# rover
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
			self.selected_point = (click_pos)
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
