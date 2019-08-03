from PyQt5 import QtWidgets, QtCore, QtGui

from devices.reach_tcp import Reach
from devices.imu_get import Orientation

import math
import random


class Canvas(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.position = None
        self.waypoints = []

    def set_position(self, position):
        self.position = position

    def set_waypoints(self, waypoints):
        self.waypoints = waypoints

    def paintEvent(self, paint_event):
        drawn_points = self.waypoints + ([] if self.position is None else [self.position])

        if len(drawn_points) == 0:
            return

        eps = 0.00000001
        lat_l, lat_h = drawn_points[0][0] - eps, drawn_points[0][0] + eps
        lon_l, lon_h = drawn_points[0][1] - eps, drawn_points[0][1] + eps

        for (lat, lon) in drawn_points:
            lat_l, lat_h = min(lat_l, lat), max(lat_h, lat)
            lon_l, lon_h = min(lon_l, lon), max(lon_h, lon)

        lon_m = (lon_l + lon_h) / 2.0
        lat_m = (lat_l + lat_h) / 2.0

        lon_scale = math.cos(math.radians(lat_m))

        margin = 40

        scale = min(
            (self.width() - 2 * margin) / (lon_scale * (lon_h - lon_l)),
            (self.height() - 2 * margin) / (lat_h - lat_l)
        )

        def to_xy(latitude, longitude):
            dx = (longitude - lon_m) * lon_scale
            dy = - (latitude - lat_m)
            x = (self.width() / 2.0) + scale * dx
            y = (self.height() / 2.0) + scale * dy
            return (x, y)

        painter = QtGui.QPainter(self)  
        pen = QtGui.QPen()
        pen.setWidth(10)
        pen.setColor(QtGui.QColor(30, 30, 30))
        painter.setPen(pen)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        
        for lat, lon in drawn_points:
            x, y = to_xy(lat, lon)
            painter.drawPoint(round(x), round(y))

        if self.position is not None:
            pen.setColor(QtGui.QColor(200, 50, 30))
            painter.setPen(pen)
            pos_lat, pos_lon = self.position
            x, y = to_xy(pos_lat, pos_lon)
            painter.drawPoint(round(x), round(y))


class PathCreator(QtWidgets.QWidget):
    def __init__(self, connected_devices={}, parent=None):
        super().__init__(parent)

        # todo change this (?)
        self.rover = None
        try:
            for name, dev in {k: v for k, v in connected_devices.items() if isinstance(v, Can)}.items():
                self.rover = rover
                break
            else:
                print('[autonomy] rover not connected')
        except Exception as e:
            print(e)

        self.last_position = None

        self.latitude_input = QtWidgets.QLineEdit('0')
        self.latitude_input.setValidator(QtGui.QDoubleValidator())
        self.longitude_input = QtWidgets.QLineEdit('0')
        self.longitude_input.setValidator(QtGui.QDoubleValidator())

        self.points = []

        self.points_listwidget = QtWidgets.QListWidget()
        add_button = QtWidgets.QPushButton('Add')
        add_button.clicked.connect(self._add_waypoint_input)
        add_current_button = QtWidgets.QPushButton('Add current location')
        add_current_button.clicked.connect(self._add_waypoint_current_location)
        remove_button = QtWidgets.QPushButton('Remove')
        remove_button.clicked.connect(self._remove_waypoint)

        start_run_button = QtWidgets.QPushButton('Start')
        start_run_button.clicked.connect(self._start_run)

        panel_widget = QtWidgets.QWidget()

        self.setLayout(QtWidgets.QHBoxLayout())

        # side panel
        panel_widget.setLayout(QtWidgets.QFormLayout())
        panel_widget.setMaximumWidth(250)

        panel_widget.layout().addRow(QtWidgets.QLabel('latitude:'), self.latitude_input)
        panel_widget.layout().addRow(QtWidgets.QLabel('longitude:'), self.longitude_input)

        panel_widget.layout().addRow(add_button, add_current_button)
        panel_widget.layout().addRow(remove_button)
        panel_widget.layout().addRow(self.points_listwidget)

        panel_widget.layout().addRow(start_run_button)

        self.layout().addWidget(panel_widget)

        # visualization
        self.map_widget = Canvas()

        self.layout().addWidget(self.map_widget)

        # start timers
        self.map_redraw_timer = QtCore.QTimer()
        self.map_redraw_timer.setSingleShot(False)
        self.map_redraw_timer.setInterval(100)
        self.map_redraw_timer.timeout.connect(self._redraw_map)
        self.map_redraw_timer.start()

    def _redraw_map(self):
        self.map_widget.set_waypoints(self.points)
        self.map_widget.set_position(self.last_position)
        self.map_widget.repaint()

    def _add_waypoint(self, latitude, longitude):
        point = (latitude, longitude)
        self.points.append(point)
        self.points_listwidget.addItem('{:.6f}, {:.6f}'.format(latitude, longitude))

    def _add_waypoint_input(self):
        latitude = float(self.latitude_input.text())
        longitude = float(self.longitude_input.text())
        self._add_waypoint(latitude, longitude)

    def _add_waypoint_current_location(self):
        if self.rover is None:
            print("[autonomy] can't obtain current rover position; no connection to the rover")
            return

        self.last_position = self.rover.get_coordinates()
        latitude, longitude = self.last_position
        self._add_waypoint(self, latitude, longitude)  

    def _remove_waypoint(self):
        row = self.points_listwidget.currentRow()
        if row == -1:
            return

        self.points.pop(row)
        self.points_listwidget.takeItem(row)

    def _start_run(self):
        if self.rover is None:
            print("[autonomy] can't start autonomous traversal; no connection to the rover")
            return

        self.rover.set_waypoints(self.points)
        self.rover.start_auto_from_waypoint(0)
