
from src.map_widget.sample_image_item import SampleImageItem
from devices.rover import Rover,relative_position_default_origin

import os
import scipy as sp
from scipy import optimize
import math
from PyQt5 import QtWidgets, QtGui, QtCore, QtSvg
from collections import OrderedDict
import jsonpickle
import numpy

epsilon = 0.000000001

PI = 3.14159265357
deg = PI / 180

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


def _create_can_poll(can, name, axis):
    return ("%s position: %d" % (name, axis), lambda axis=axis: can.get_position()[axis])



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
        hlayout1.addWidget(self.viewwidget)

        hlayout2 = QtWidgets.QHBoxLayout()

        hlayout2.addWidget(QtWidgets.QLabel("x:"))
        self.xwidget = QtWidgets.QLineEdit()
        self.xwidget.setEnabled(False)
        hlayout2.addWidget(self.xwidget)
        hlayout2.addSpacing(20)
        hlayout2.addWidget(QtWidgets.QLabel("y:"))
        self.ywidget = QtWidgets.QLineEdit()
        self.ywidget.setEnabled(False)
        hlayout2.addWidget(self.ywidget)
        hlayout2.addSpacing(20)
        hlayout2.addWidget(QtWidgets.QLabel("lon:"))
        self.lonwidget = QtWidgets.QLineEdit()
        self.lonwidget.setEnabled(False)
        hlayout2.addWidget(self.lonwidget)
        hlayout2.addSpacing(20)
        hlayout2.addWidget(QtWidgets.QLabel("lat:"))
        self.latwidget = QtWidgets.QLineEdit()
        self.latwidget.setEnabled(False)
        hlayout2.addWidget(self.latwidget)
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

        try:
            from devices.rover import Rover
            for name, can in {k: v for k, v in self.device_list.items() if isinstance(v, Rover)}.items():
                self.can = can
        except Exception as e:
            print(e)

        self.slopepoints = []

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
            origin = relative_position_default_origin
            self.latwidget.setText(str(round(origin[0] + position.y()/(6371000*deg), 6)))
            self.lonwidget.setText(str(round(origin[1] + position.x() / math.cos(deg*origin[0]+position.y()/6371000)/(6371000*deg), 6)))
            QtWidgets.QGraphicsScene.mouseMoveEvent(self.scene, event)  # propagate to objects in scene

        self.scene.mouseMoveEvent = onMouseMoveEvent

    def start(self, activate=True):
        self.active = activate

    def refreshCombos(self):
        self.start(False)
        self.pools = []
        self.slaves = []

        try:
            from devices.rover import Rover
            for name, can in {k: v for k, v in self.device_list.items() if isinstance(v, Rover)}.items():
                self.pools.append(_create_can_poll(can, "x", 0))
                self.pools.append(_create_can_poll(can, "y", 1))
        except Exception as e:
            print(e)

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
            '''
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
            
            '''
            '''
            try:
                tags = self.can.tags()
            except Exception:
                tags = [None for i in range(15)]
                print("error while loading tags list")
            
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
                pass'''

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