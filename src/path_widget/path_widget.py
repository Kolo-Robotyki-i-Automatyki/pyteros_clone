from PyQt5 import QtWidgets, QtCore, QtGui

from devices.reach_tcp import Reach
from devices.imu_get import Orientation

import random

class PathCreator(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # self.gps = Reach()
        # self.compass = Orientation()

        self.orientation_label = QtWidgets.QLabel('')
        self.latitude_label = QtWidgets.QLabel('')
        self.longitude_label = QtWidgets.QLabel('')

        self.heading = 0.0
        self.latitude = 0.0
        self.longitude = 0.0

        self.points = []

        self.map_markers = []

        self.points_listwidget = QtWidgets.QListWidget()
        add_button = QtWidgets.QPushButton('Add')
        add_button.clicked.connect(self._add_waypoint)
        remove_button = QtWidgets.QPushButton('Remove')
        remove_button.clicked.connect(self._remove_waypoint)

        start_run_button = QtWidgets.QPushButton('Start')
        start_run_button.clicked.connect(self._start_run)

        panel_widget = QtWidgets.QWidget()

        self.setLayout(QtWidgets.QHBoxLayout())

        # side panel
        panel_widget.setLayout(QtWidgets.QFormLayout())
        panel_widget.setMaximumWidth(250)

        panel_widget.layout().addRow(QtWidgets.QLabel('latitude:'), self.latitude_label)
        panel_widget.layout().addRow(QtWidgets.QLabel('longitude:'), self.longitude_label)
        panel_widget.layout().addRow(QtWidgets.QLabel('heading:'), self.orientation_label)

        panel_widget.layout().addRow(add_button, remove_button)
        panel_widget.layout().addRow(self.points_listwidget)

        panel_widget.layout().addRow(start_run_button)

        self.layout().addWidget(panel_widget)

        # visualization
        self.map_widget = QtWidgets.QWidget()

        self.layout().addWidget(self.map_widget)

        # start timers
        self.position_update_timer = QtCore.QTimer()
        self.position_update_timer.setSingleShot(False)
        self.position_update_timer.setInterval(100)
        self.position_update_timer.timeout.connect(self._update_position_and_heading)
        self.position_update_timer.start()

        self.map_redraw_timer = QtCore.QTimer()
        self.map_redraw_timer.setSingleShot(False)
        self.map_redraw_timer.setInterval(100)
        self.map_redraw_timer.timeout.connect(self._redraw_map)
        self.map_redraw_timer.start()

    def _update_position_and_heading(self):
        # gsp_status = self.reach.get_status()
        # compass_status = self.compass.get_orientation() 

        self.latitude = random.uniform(-90.0, 90.0)
        self.longitude = random.uniform(-180.0, 180.0)
        self.heading = random.uniform(0.0, 360.0)

        self.orientation_label.setText('{}°'.format(int(self.heading)))
        self.latitude_label.setText('{:.6f}°'.format(self.latitude))
        self.longitude_label.setText('{:.6f}°'.format(self.longitude))

    def _redraw_map(self):
        pass

    def _add_waypoint(self):
        point = (self.latitude, self.longitude)
        self.points.append(point)
        self.points_listwidget.addItem('{:.6f}, {:.6f}'.format(self.latitude, self.longitude))

    def _remove_waypoint(self):
        row = self.points_listwidget.currentRow()
        if row == -1:
            return

        self.points.pop(row)
        self.points_listwidget.takeItem(row)

    def _start_run(self):
        pass

