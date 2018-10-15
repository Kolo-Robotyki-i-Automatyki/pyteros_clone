
from src.map_widget.map_area_item import MapAreaItem, epsilon
from src.map_widget.sample_image_item import SampleImageItem
from devices.can import Can

import os
import scipy as sp
from scipy import optimize
import math
from PyQt5 import QtWidgets, QtGui, QtCore, QtSvg
from collections import OrderedDict
import jsonpickle
import numpy

epsilon = 0.000000001


class ZoomableGraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setTransform(self.transform().scale(1, -1))

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.list_key_on = []
        self.list_key_pressed = []
        self.list_key_released = []
        self.arrow_navigation_timer = QtCore.QTimer()
        self.arrow_navigation_timer.timeout.connect(self.loop_arrow_navigation)
        self.arrow_navigation_interval = 25
        self.arrow_navigation_timer.setInterval(self.arrow_navigation_interval)
        self.arrow_navigation_timer.start()
        # self.resizeEvent.connect(self.refresh_geometry_change)

    # def resizeEvent(self, geometry):
    #    self.setSceneRect(QtCore.QRectF(self.geometry()))

    def keyPressEvent(self, event):
        self.list_key_on.append(event.key())
        self.list_key_pressed.append(event.key())
        event.accept()

    def keyReleaseEvent(self, event):
        self.list_key_on.remove(event.key())
        self.list_key_released.append(event.key())
        event.accept()

    def loop_arrow_navigation(self):
        dx = dy = 0
        if QtCore.Qt.Key_Up in self.list_key_on:
            dy += 1
        if QtCore.Qt.Key_Down in self.list_key_on:
            dy -= 1
        if QtCore.Qt.Key_Left in self.list_key_on:
            dx -= 1
        if QtCore.Qt.Key_Right in self.list_key_on:
            dx += 1
        if dx != 0 or dy != 0:
            zoom = math.sqrt(abs(self.transform().determinant()))

            step = (
                           self.sceneRect().width() + self.sceneRect().height()) / 2 * self.arrow_navigation_interval / 1000 / zoom  # 1 screen/s
            self.setSceneRect(self.sceneRect().x() + dx * step, self.sceneRect().y() + dy * step,
                              self.sceneRect().width(), self.sceneRect().height())

            viewCenter = self.mapToScene(self.width() / 2., self.height() / 2.)
            viewCenter += QtCore.QPointF(dx * step, dy * step)
            self.centerOn(viewCenter)

        self.list_key_pressed = []
        self.list_key_released = []

    def wheelEvent(self, event):
        # Zoom Factor
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor

        # Set Anchors
        #   self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        # self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)

        # Save the scene pos
        oldPos = self.mapToScene(event.pos())

        # Zoom
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.scale(zoomFactor, zoomFactor)

        # Get the new position
        newPos = self.mapToScene(event.pos())
        # Move scene to old position
        delta = newPos - oldPos

        old_transform = self.transform()
        scene_rect = self.sceneRect()

        self.setSceneRect(scene_rect.x() - delta.x(), scene_rect.y() - delta.y(), scene_rect.width(),
                          scene_rect.height())
        self.setTransform(old_transform)


def _create_apt_poll(apt, name, serial):
    """Creates a pair of a name and a function to get stage position """
    func = lambda: apt.position(serial)
    return ("APT %s, s/n: %d" % (name, serial), func)


def _create_anc350_poll(anc350, name, axis):
    """Creates a pair of a name and a function to get stage position """

    def f():
        return anc350.axisPos(axis)

    return ("Attocube %s axis: %d" % (name, axis), f)


def _create_can_poll(can, name, axis):
    """Creates a pair of a name and a function to get stage position """

    def f():
        return can.get_position(axis)

    return ("%s position: %d" % (name, axis), f)



class MapWidget(QtWidgets.QWidget):
    def __init__(self, device_list, parent=None):
        super().__init__(parent)
        self.device_list = device_list
        self.slaves = []
        self.pools = []
        self.bg_item = None

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.timeout)
        self.timer.start()
        self.active = False

        layout = QtWidgets.QVBoxLayout()  # main vertical layout
        self.setLayout(layout)
        hlayout1 = QtWidgets.QHBoxLayout()  # horizontal layout for graphics view and mapping
        layout.addLayout(hlayout1)
        self.viewwidget = ZoomableGraphicsView(self)
        self.setupScene()

        self.map_area_scroll = QtWidgets.QScrollArea()
        self.map_area_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.map_area_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.map_area_scroll.setWidgetResizable(True)
        map_area_scroll_frame = QtWidgets.QFrame(self.map_area_scroll)
        self.map_area_scroll.setWidget(map_area_scroll_frame)
        self.map_area_scroll.setFixedWidth(175)
        self.map_area_scroll.setVisible(False)
        map_area_buttons_layout = QtWidgets.QHBoxLayout()

        self.map_area_layout = QtWidgets.QVBoxLayout()
        map_area_scroll_frame.setLayout(self.map_area_layout)

        self.label_total_map_count = QtWidgets.QLabel()
        self.map_area_layout.addWidget(self.label_total_map_count)

        self.check_box_snap = QtWidgets.QCheckBox("Snap to grid")
        self.check_box_snap.setChecked(True)
        self.map_area_layout.addWidget(self.check_box_snap)
        self.map_area_layout.addLayout(map_area_buttons_layout)
        self.map_area_layout.addStretch(10)

        self.map_area_items = []
        self.button_add_map_area = QtWidgets.QPushButton("Add")
        self.button_add_map_area.setFixedWidth(65)
        map_area_buttons_layout.addWidget(self.button_add_map_area)
        self.button_add_map_area.clicked.connect(self.add_map_area)
        self.button_delete_map_area = QtWidgets.QPushButton("Delete")
        self.button_delete_map_area.setFixedWidth(65)
        map_area_buttons_layout.addWidget(self.button_delete_map_area)
        self.button_delete_map_area.setEnabled(False)
        self.button_delete_map_area.clicked.connect(self.delete_map_area)

        hlayout1.addWidget(self.map_area_scroll)

        hlayout1.addWidget(self.viewwidget)

        hlayout2 = QtWidgets.QHBoxLayout()

        check_box_enable_map = QtWidgets.QCheckBox("Show mapping panel")
        check_box_enable_map.stateChanged.connect(self.map_area_scroll.setVisible)
        hlayout2.addWidget(check_box_enable_map)
        hlayout2.addStretch(10)

        hlayout2.addWidget(QtWidgets.QLabel("x:"))
        self.xwidget = QtWidgets.QLineEdit()
        self.xwidget.setEnabled(False)
        hlayout2.addWidget(self.xwidget)
        hlayout2.addSpacing(20)
        hlayout2.addWidget(QtWidgets.QLabel("y:"))
        self.ywidget = QtWidgets.QLineEdit()
        self.ywidget.setEnabled(False)
        hlayout2.addWidget(self.ywidget)
        layout.addLayout(hlayout2)
        self.show()

        self.pixmapItem = None

        self.bg_item = SampleImageItem(self)
        layout.addWidget(self.bg_item.widget)

        hlayout3 = QtWidgets.QHBoxLayout()

        self.combos = {}
        for direction in ("x", "y"):
            hlayout3.addWidget(QtWidgets.QLabel(direction + ":"))
            combo = QtWidgets.QComboBox()
            combo.addItem("None")
            combo.setMinimumWidth(200)
            hlayout3.addWidget(combo)
            self.combos[direction] = combo
            hlayout3.addSpacing(20)
        hlayout3.addStretch(5)
        layout.addLayout(hlayout3)

        hlayout4 = QtWidgets.QHBoxLayout()
        self.refreshButton = QtWidgets.QPushButton("Refresh")
        self.refreshButton.clicked.connect(self.refreshCombos)
        hlayout4.addWidget(self.refreshButton)
        self.startButton = QtWidgets.QPushButton("Start control")
        self.startButton.setCheckable(True)
        self.startButton.clicked.connect(self.start)
        self.startButton.clicked.connect(self.saveSettings)
        hlayout4.addWidget(self.startButton)
        hlayout4.addStretch(1)
        layout.addLayout(hlayout4)

        self.can = Can(req_port=10200, pub_port=10201, host="10.1.1.200")
        self.slopepoints = []

    def delete_duplicated_points(self, points):
        order_function = lambda p: p[0] * 100 * numpy.pi + p[1]
        points.sort(key=order_function)  # low probability of equal points
        if len(points) == 0:
            unique = []
        else:
            unique = [points[0]]
            for i in range(1, len(points)):
                duplicate = False
                j = -1
                while j >= - len(unique) and order_function(unique[j]) > order_function(points[i]) - epsilon:
                    if math.sqrt((unique[j][0] - points[i][0]) ** 2 + (unique[j][1] - points[i][1]) ** 2) < epsilon:
                        duplicate = True
                        break
                    j -= 1
                if not duplicate:
                    unique.append(points[i])
        return unique

    def update_label_total_map_count(self):
        points = []
        for map_area in self.map_area_items:
            new_points = map_area.get_positions()
            if len(new_points) > 30000:
                self.label_total_map_count.setText(">30000 points total.")
                return
            points += new_points
        unique = self.delete_duplicated_points(points)
        self.label_total_map_count.setText(str(len(unique)) + " points total.")

    def add_map_area(self):
        if len(self.map_area_items) == 0:
            self.button_delete_map_area.setEnabled(True)

        tr = self.viewwidget.mapToScene(QtCore.QPoint(self.viewwidget.width(), 0))
        bl = self.viewwidget.mapToScene(QtCore.QPoint(0, self.viewwidget.height()))
        w = (tr.x() - bl.x()) / 3
        h = (tr.y() - bl.y()) / 3
        x = bl.x() + w
        y = bl.y() + h
        step = max(10 ** math.floor(math.log10(min(w, h) / 10)), \
                   2 * 10 ** math.floor(math.log10(min(w, h) / 10 / 2)), \
                   5 * 10 ** math.floor(math.log10(min(w, h) / 10 / 5)))
        x = step * math.floor(x / step)
        y = step * math.floor(y / step)
        w = step * math.floor(w / step)
        h = step * math.floor(h / step)

        map_area = MapAreaItem(self, x, y, w, h, step, step)

        self.map_area_layout.removeItem(self.map_area_layout.itemAt( \
            self.map_area_layout.count() - 1))
        self.map_area_layout.insertWidget(-3, map_area.widget)
        self.map_area_layout.addStretch(10)
        self.map_area_items.append(map_area)
        self.update_label_total_map_count()

    def delete_map_area(self):
        if len(self.map_area_items) == 1:
            self.button_delete_map_area.setEnabled(False)
        self.scene.removeItem(self.map_area_items[-1])
        self.map_area_items[-1].widget.setVisible(False)
        self.map_area_layout.removeWidget(self.map_area_items[-1].widget)
        self.map_area_items.pop(-1)

    def loadSettings(self):
        try:
            with open("config" + os.sep + "map_widget.cfg", "r") as file:
                axes = jsonpickle.decode(file.read())
                for direction in axes:
                    self.combos[direction].setCurrentText(axes[direction])

        except Exception as e:
            self.saveSettings()
            print(e)

    def saveSettings(self):
        try:
            with open("config" + os.sep + "map_widget.cfg", "w") as file:
                axes = {direction: self.combos[direction].currentText() for direction in self.combos}
                file.write(jsonpickle.encode(axes))
        except Exception as e:
            print(e)

    def setupScene(self):
        self.scene = QtWidgets.QGraphicsScene()
        self.viewwidget.setScene(self.scene)

        self.cursor = QtWidgets.QGraphicsItemGroup()
        self.cursor.setZValue(100)
        circle = QtWidgets.QGraphicsEllipseItem(self.cursor)
        circle.setRect(-5, -5, 10, 10)
        circle.setBrush(QtGui.QBrush(QtCore.Qt.red))
        circle.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self.scene.addItem(self.cursor)

        def onMouseMoveEvent(event):
            position = QtCore.QPointF(event.scenePos())
            self.xwidget.setText(str(position.x()))
            self.ywidget.setText(str(position.y()))
            QtWidgets.QGraphicsScene.mouseMoveEvent(self.scene, event)  # propagate to objects in scene

        self.scene.mouseMoveEvent = onMouseMoveEvent

    def start(self, activate=True):
        self.active = activate

    def refreshCombos(self):
        self.start(False)
        self.pools = []
        self.slaves = []

        try:
            from devices.thorlabs.apt import APT
            for name, apt in {k: v for k, v in self.device_list.items() if isinstance(v, APT)}.items():
                for serial in apt.devices():
                    self.pools.append(_create_apt_poll(apt, name, serial))
        except Exception as e:
            print(e)

        try:
            from devices.attocube.anc350 import ANC350
            for name, anc350 in {k: v for k, v in self.device_list.items() if isinstance(v, ANC350)}.items():
                for axis in anc350.axes():
                    self.pools.append(_create_anc350_poll(anc350, name, axis))
        except Exception as e:
            print(e)

        try:
            from devices.can import Can
            for name, can in {k: v for k, v in self.device_list.items() if isinstance(v, Can)}.items():
                self.pools.append(_create_can_poll(can, "x", 0))
                self.pools.append(_create_can_poll(can, "y", 1))
        except Exception as e:
            print(e)

        '''from ..can import Can
            for devname, can in {k: v for k, v in self.device_list.items() if isinstance(v, Can)}.items():
                for name, id in can.axes():
                    description = name + "(" + str(id) + ")"
                    self.slaves.append(Slave(can, description, id, step=False, method="power"))
                self.slaves.append(Slave(can, "throttle", 0, step=False, method="drive"))
                self.slaves.append(Slave(can, "turning right", 1, step=False, method="drive"))'''

        for direction, combo in self.combos.items():
            n = combo.currentIndex()
            combo.clear()
            combo.addItem("None", lambda: None)
            for name, func in self.pools:
                combo.addItem(name, func)
            combo.setCurrentIndex(n)

        self.loadSettings()

    def timeout(self):
        if self.active:
            try:
                for point in self.slopepoints:
                    self.scene.removeItem(point)
                    del point
            except Exception:
                print("failed slopepiin")
            self.slopepoints = []

            try:
                list = self.can.slope_points()
            except Exception:
                print("error while loading slope list")
                list = []

            for p in list:
                point = QtWidgets.QGraphicsItemGroup()
                point.setZValue(90)
                circle = QtWidgets.QGraphicsEllipseItem(point)
                circle.setRect(-5, -5, 10, 10)

                circle.setBrush(QtGui.QBrush(QtCore.Qt.blue))
                circle.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
                point.setX(p[0])
                point.setY(p[1])
                self.scene.addItem(point)
                self.slopepoints.append(point)

            try:
                tags = self.can.tags()
            except Exception:
                tags = [None for i in range(15)]
                print("error while loading tags list")

            try:
                pos = (self.can.get_position(0), self.can.get_position(1))
            except Exception:
                pos = (-1, -2)
                print("error while loading tpositiont")

            try:

                for i in range(35):
                    if tags[i] != None:
                        tag = QtWidgets.QGraphicsItemGroup()
                        # tag.setTransform(tag.transform().rotate(tags[i][0]))
                        tag.setZValue(90)
                        rect = QtWidgets.QGraphicsRectItem(tag)
                        rect.setRect(-0.1, -0.1, 0.2, 3 * tags[i][1])
                        tag.setScale(0.3)
                        tag.setRotation(-tags[i][0] * 180 / 3.1415)
                        print(tags[i][0])
                        rect.setBrush(QtGui.QBrush(QtCore.Qt.green))
                        tag.setX(pos[0])
                        tag.setY(pos[1])
                        self.scene.addItem(tag)
                        self.tags.append(tag)

                        io = QtWidgets.QGraphicsTextItem()
                        io.setTransform(io.transform().scale(0.3, -0.3))
                        io.setPos(pos[0] + tags[i][1], pos[1])
                        io.setPlainText(str(i))

                        self.scene.addItem(io)
                        self.tags.append(io)
            except Exception:
                pass

            for direction, combo in self.combos.items():
                if combo.currentText() == "None":
                    return
                device_id = combo.currentIndex() - 1
                # print(self.pools[device_id][0])
                try:
                    if direction == "x":
                        self.cursor.setX(self.pools[device_id][1]())
                    else:
                        self.cursor.setY(self.pools[device_id][1]())
                except Exception:
                    pass


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    okno = MapWidget([])
    sys.exit(app.exec_())