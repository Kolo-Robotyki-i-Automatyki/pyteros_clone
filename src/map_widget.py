# -*- coding: utf-8 -*-
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


class AnchorItem(QtWidgets.QGraphicsItemGroup):
    def __init__(self, parent, real_pos):
        super().__init__(parent)
        self.setEnabled(True)
        self.setActive(True)
        circle = QtWidgets.QGraphicsEllipseItem(self)
        circle.setRect(-5, -5, 10, 10)
        circle.setBrush(QtGui.QBrush(QtCore.Qt.yellow))
        circle.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self.real_pos = real_pos

    def contextMenuEvent(self, event):
        event.accept()
        menu = QtWidgets.QMenu()
        removeAction = menu.addAction("Remove anchor point")
        selectedAction = menu.exec(event.screenPos())
        if selectedAction == removeAction:
            self.parentItem().remove_anchor(self, save = True)


class SampleImageItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, parent):
        super().__init__()

        self.parent = parent
        self.scene = self.parent.scene
        self.loaded = False
        self.anchor_items = []

        self.widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.widget.setLayout(layout)

        button_load = QtWidgets.QPushButton("Load image")
        layout.addWidget(button_load, 0, 0)
        button_load.clicked.connect(self.loadImage)

        button_fit = QtWidgets.QPushButton("Fit Transform")
        layout.addWidget(button_fit, 1, 0)
        button_fit.clicked.connect(self.find_best_transform)

        self.sides = OrderedDict([("x", -100), ("y", 100), ("rotation", 0), ("width", 100), ("aspect ratio", 1)])
        self.edits = OrderedDict([])
        self.checks = OrderedDict([])
        col = 1
        for s in self.sides:
            layout.addWidget(QtWidgets.QLabel(s + ":"), 0, 2 * col - 1)

            edit = QtWidgets.QLineEdit(str(self.sides[s]))
            edit.setValidator(QtGui.QDoubleValidator())
            layout.addWidget(edit, 1, 2 * col - 1, 1, 2)
            edit.setFixedWidth(120)
            edit.editingFinished.connect(self.updatePixmap)
            edit.editingFinished.connect(self.save_settings)
            self.edits[s] = edit

            check = QtWidgets.QCheckBox("Fit")
            layout.addWidget(check, 0, 2 * col)
            self.checks[s] = check

            col += 1

        for i in ["x", "y", "width", "rotation"]:
            self.checks[i].setChecked(1)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        add_anchor_action = menu.addAction("Anchor this point")
        remove_action = menu.addAction("Remove map")
        selected_action = menu.exec(event.screenPos())
        if selected_action == remove_action:
            pass
        elif selected_action == add_anchor_action:
            dialog = QtWidgets.QDialog()
            dialog.setWindowTitle("Anchor this point")
            layout = QtWidgets.QFormLayout()
            dialog.setLayout(layout)
            x_input = QtWidgets.QLineEdit(str(self.parent.cursor.x()))
            layout.addRow("X coordinate", x_input)
            y_input = QtWidgets.QLineEdit(str(self.parent.cursor.y()))
            layout.addRow("Y coordinate", y_input)
            buttonBox = QtWidgets.QDialogButtonBox()
            buttonBox.setOrientation(QtCore.Qt.Horizontal)
            buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
            buttonBox.accepted.connect(dialog.accept)
            buttonBox.rejected.connect(dialog.reject)
            layout.addRow(buttonBox)

            # d.setWindowModality(Qt.ApplicationModal)
            dialog.show()
            if dialog.exec_():
                real_pos = (float(x_input.text()), float(y_input.text()))
                anchor = AnchorItem(self, real_pos)
                pos = self.mapFromScene(event.scenePos())
                anchor.setPos(pos)
                self.anchor_items.append(anchor)
                self.save_settings()

    def loadImage(self):
        self.pixmap = QtGui.QPixmap()
        fileName = QtWidgets.QFileDialog.getOpenFileName(self.parent, "Load sample image",
                                                         "", "Image Files (*.png *.jpg *.bmp *.svg)")
        fileName = fileName[0]

        self.config_filename = fileName + ".cfg"

        if not fileName:
            return

        if self.loaded:
            self.scene.removeItem(self)
            del (self.pixmap)
            self.loaded = False
        try:
            if fileName.lower().endswith("svg"):
                self.bg_item = QtSvg.QGraphicsSvgItem(fileName)
            else:
                print("case2")
                pixmap = QtGui.QPixmap(fileName)
                pixmap = pixmap.transformed(QtGui.QTransform().scale(1, -1))
                self.w = pixmap.width()
                self.h = pixmap.height()
                self.setPixmap(pixmap)
            self.scene.addItem(self)
            self.setEnabled(True)
            self.setActive(True)
            self.loaded = True
            self.setAcceptedMouseButtons(QtCore.Qt.RightButton)
            self.current_coordinates = (0, 0)
            self.load_settings()
            self.updatePixmap()
        except Exception as e:
            print("Error: ", str(e))

    def updatePixmap(self):
        if self.loaded:
            transform_params = [float(self.edits[key].text()) for key in list(self.sides)]
            transform = QtGui.QTransform()
            transform.translate(transform_params[0], transform_params[1])
            transform.rotate(transform_params[2])
            transform.scale(transform_params[3],
                            transform_params[3] / transform_params[4] / (float(self.w) / float(self.h)))
            transform.scale(1 / self.w, 1 / self.h)
            self.setTransform(transform)

    def load_settings(self):
        try:
            with open(self.config_filename, "r") as file:
                transform_params, anchors = jsonpickle.decode(file.read())

                for anchor in self.anchor_items:
                    self.remove_anchor(anchor, save = False)
                for a in anchors:
                    real_pos, pos = a
                    anchor = AnchorItem(self, real_pos)
                    anchor.real_pos = a[0]
                    anchor.setPos(QtCore.QPointF(pos[0], pos[1]))
                    self.anchor_items.append(anchor)

                keys = list(self.sides)
                for i in range(len(keys)):
                    self.edits[keys[i]].setText(str(transform_params[i]))
        except Exception as e:
            print(e)

    def save_settings(self):
        try:
            with open(self.config_filename, "w") as file:
                anchors = [(a.real_pos, (a.pos().x(), a.pos().y())) for a in self.anchor_items]
                transform_params = [float(self.edits[key].text()) for key in list(self.sides)]
                file.write(jsonpickle.encode([transform_params, anchors]))
        except Exception as e:
            print(e)

    def remove_anchor(self, anchor_item, save = False):
        self.anchor_items.remove(anchor_item)
        anchor_item.setParentItem(None)
        anchor_item.scene().removeItem(anchor_item)
        if save:
            self.save_settings()

    def find_best_transform(self):
        """ Use least squares method to find the best transform which fits the anchor points"""
        if len(self.anchor_items) < 1:
            return

        keys = list(self.sides)
        transform_params = [float(self.edits[key].text()) for key in keys]
        free_params_index = []  # indexes of free params
        free_params_initial = []
        for i in range(len(keys)):  # take at most first 2*n free parameters when there are n anchors
            if self.checks[keys[i]].isChecked() and len(free_params_index) < 2 * len(self.anchor_items):
                free_params_index.append(i)
                free_params_initial.append(transform_params[i])
        # print("init params ", free_params_initial, " free_params_index ", free_params_index)
        data = [(a.pos(), a.real_pos) for a in self.anchor_items]

        def update_transform_params(params):
            j = 0
            for i in free_params_index:
                transform_params[i] = params[j]
                j += 1

        def build_transform(params):
            update_transform_params(params)
            transform = QtGui.QTransform()
            transform.translate(transform_params[0], transform_params[1])
            transform.rotate(transform_params[2])
            transform.scale(transform_params[3],
                            transform_params[3] / transform_params[4] / (float(self.w) / float(self.h)))
            transform.scale(1 / self.w, 1 / self.h)
            return transform

        def fitfunc(params):
            transform = build_transform(params)
            chi2 = 0.
            for point0, point1 in data:
                diff = QtCore.QPointF(point1[0], point1[1]) - transform.map(point0)
                chi2 += diff.x() ** 2 + diff.y() ** 2
            return chi2

        best = optimize.fmin(fitfunc, free_params_initial)
        update_transform_params(best)
        for i in range(len(keys)):
            self.edits[keys[i]].setText(str(transform_params[i]))
        self.updatePixmap()
        self.save_settings()


class MapAreaItem(QtWidgets.QGraphicsItem):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.scene = parent.scene
        self.setZValue(10)

        self.scene.addItem(self)

        self.setAcceptHoverEvents(True)
        self.border_size = 15
        self.hover = None
        self.drag = None
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable | QtWidgets.QGraphicsItem.ItemIsFocusable)

        layout = QtWidgets.QGridLayout()
        self.widget = QtWidgets.QFrame()
        self.widget.setFrameShape(QtWidgets.QFrame.Box)
        self.widget.setLayout(layout)
        self.widget.setSizePolicy(QtWidgets.QSizePolicy())

        self.label_map_size = QtWidgets.QLabel()
        layout.addWidget(self.label_map_size, 0, 0, 1, 2)

        self.sides = OrderedDict(
            [("x", -100), ("y", 100), ("width", 200), ("height", 150), ("rotation", 0), ("step_x", 10), ("step_y", 10)])
        self.edits = OrderedDict([])

        col = 1
        for s in self.sides:
            layout.addWidget(QtWidgets.QLabel(s + ":"), col, 0)
            edit = QtWidgets.QLineEdit(str(self.sides[s]))
            edit.setValidator(QtGui.QDoubleValidator())
            layout.addWidget(edit, col, 1)
            edit.setFixedWidth(70)
            edit.editingFinished.connect(self.update_transform)
            edit.editingFinished.connect(self.scene.update)
            self.edits[s] = edit
            col += 1

        for s in self.sides:
            self.edits[s].textChanged.connect(self.update_label_map_size)
            self.edits[s].textChanged.connect(self.parent.update_label_total_map_count)

        self.update_label_map_size()
        self.parent.update_label_total_map_count()
        self.update_transform()

    def set_parameter(self, parameter, value):
        if value == 0:
            self.edits[parameter].setText("0")
        else:
            self.edits[parameter].setText(str(round(value, 7 - int(math.floor(math.log10(abs(value)))))))
        self.update_transform()

    def get_parameter(self, parameter):
        return float(self.edits[parameter].text())

    def update_border_rect(self, zoom):
        rect = self.boundingRect()
        dx = QtCore.QPointF(self.border_size / zoom, 0)
        dy = QtCore.QPointF(0, -self.border_size / zoom)  # minus because y axis inversion
        self.border_rect = {}
        self.border_rect_ordered_keys = ['c', 'l', 'b', 'r', 't', 'bl', 'tl', 'br', 'tr']
        self.border_rect['bl'] = QtCore.QRectF(rect.topLeft(), rect.topLeft() + dx - dy)  # top/bottom - y inversion
        self.border_rect['br'] = QtCore.QRectF(rect.topRight(), rect.topRight() - dx - dy)
        self.border_rect['tr'] = QtCore.QRectF(rect.bottomRight(), rect.bottomRight() - dx + dy)
        self.border_rect['tl'] = QtCore.QRectF(rect.bottomLeft(), rect.bottomLeft() + dx + dy)
        self.border_rect['b'] = QtCore.QRectF(rect.topLeft() + dx, rect.topRight() - dx - dy)
        self.border_rect['r'] = QtCore.QRectF(rect.topRight() - dy, rect.bottomRight() - dx + dy)
        self.border_rect['t'] = QtCore.QRectF(rect.bottomRight() - dx, rect.bottomLeft() + dx + dy)
        self.border_rect['l'] = QtCore.QRectF(rect.bottomLeft() + dy, rect.topLeft() + dx - dy)
        self.border_rect['c'] = QtCore.QRectF(rect.bottomLeft() + dx + dy, rect.topRight() - dx - dy)

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self.get_parameter("width"), self.get_parameter("height"))

    def update_transform(self):
        transform = QtGui.QTransform()
        transform.translate(self.get_parameter("x"), self.get_parameter("y"))
        transform.rotate(self.get_parameter("rotation"))
        self.setTransform(transform)

    def hoverEnterEvent(self, event):
        self.refresh_hover_rect(event.pos())

    def hoverLeaveEvent(self, event):
        self.hover = None
        self.update()
        self.scene.update()

    def hoverMoveEvent(self, event):
        self.refresh_hover_rect(event.pos())

    def refresh_hover_rect(self, mouse_pos):
        self.hover = None
        for rect in self.border_rect_ordered_keys:  # rectangles can overlap for small zoom, ordering prefers corners for easy resize
            if self.border_rect[rect].contains(mouse_pos):
                self.hover = rect

        self.scene.update()

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.drag = None
        self.refresh_hover_rect(event.pos())
        self.drag = self.hover
        self.drag_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.refresh_hover_rect(event.pos())
        self.drag = None

    def mouseMoveEvent(self, event):
        if self.drag != None:
            flip_x = {'l': 'r', 'tl': 'tr', 't': 't', 'tr': 'tl', 'r': 'l', 'br': 'bl', 'b': 'b', 'bl': 'br'}
            flip_y = {'l': 'l', 'tl': 'bl', 't': 'b', 'tr': 'br', 'r': 'r', 'br': 'tr', 'b': 't', 'bl': 'tl'}
            v = event.pos() - self.drag_pos

            x = 0
            y = 0
            width = self.get_parameter("width")
            height = self.get_parameter("height")

            if self.drag == 'c':
                x += v.x()
                y += v.y()

            if self.drag == 'l' or self.drag == 'tl' or self.drag == 'bl':
                x += v.x()
                width -= v.x()
            if self.drag == 'r' or self.drag == 'tr' or self.drag == 'br':
                width += v.x()
                self.drag_pos.setX(self.drag_pos.x() + v.x())
            if self.drag == 'b' or self.drag == 'bl' or self.drag == 'br':
                y += v.y()
                height -= v.y()
            if self.drag == 't' or self.drag == 'tl' or self.drag == 'tr':
                height += v.y()
                self.drag_pos.setY(self.drag_pos.y() + v.y())

            if width < 0:
                self.drag = self.hover = flip_x[self.drag]
                width = -width
                x -= width
                self.drag_pos.setX(self.drag_pos.x() + width)
            if height < 0:
                self.drag = self.hover = flip_y[self.drag]
                height = -height
                y -= height
                self.drag_pos.setY(self.drag_pos.y() + height)


            new_pos = self.transform().map(QtCore.QPointF(x, y))
            self.set_parameter("x", new_pos.x())
            self.set_parameter("y", new_pos.y())
            self.set_parameter("width", width)
            self.set_parameter("height", height)

            self.scene.update()
            self.update()

    def map_origin(self): #defines offset of grid of map points, in map area coordinates
        if self.parent.check_box_snap.isChecked():
            a = math.radians(self.get_parameter("rotation"))
            x = self.get_parameter("x")
            y = self.get_parameter("y")
            return (- x * math.cos(a) - y * math.sin(a), - y * math.cos(a) + x * math.sin(a))
        else:
            return (0, 0)

    def map_area_parameters(self):
        x0, y0 = self.map_origin()
        width = self.get_parameter("width")
        height = self.get_parameter("height")
        step_x = self.get_parameter("step_x")
        step_y = self.get_parameter("step_y")
        end_x = math.floor((width - x0) / step_x + epsilon + 1)
        end_y = math.floor((height - y0) / step_y + epsilon + 1)
        begin_x = math.floor((-x0) / step_x - epsilon + 1)
        begin_y = math.floor((-y0) / step_y - epsilon + 1)
        rotation = self.get_parameter("rotation")
        return (x0, y0, width, height, step_x, step_y, end_x, end_y, begin_x, begin_y, rotation)

    def update_label_map_size(self):
        end_x, end_y, begin_x, begin_y = self.map_area_parameters()[6:10]
        s = str(end_x - begin_x) + "x" + str(end_y - begin_y) + ", total: " + str((end_x - begin_x)*(end_y - begin_y))
        self.label_map_size.setText(s)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        zoom = option.levelOfDetailFromTransform(painter.worldTransform())

        self.update_border_rect(zoom)

        pen = QtGui.QPen()
        pen.setCosmetic(True)  # fixed width regardless of transformations
        pen.setColor(QtGui.QColor(128, 128, 128))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())
        if self.hover != None:
            painter.drawRect(self.border_rect[self.hover])

        max_grid = max(zoom * self.get_parameter("step_x"), zoom * self.get_parameter("step_y"))
        min_grid = min(zoom * self.get_parameter("step_x"), zoom * self.get_parameter("step_y"))
        if max_grid > 6 and min_grid > 3:

            x0, y0, width, height, step_x, step_y, end_x, end_y, begin_x, begin_y, rotation = self.map_area_parameters()

            pen = QtGui.QPen()
            pen.setCosmetic(True)  # fixed width regardless of transformations
            pen.setColor(QtGui.QColor(255, 0, 0))
            pen.setWidth(max(2, min(7, max_grid / 5)))
            painter.setPen(pen)

            if (end_x - begin_x) * (end_y - begin_y) < 100000:
                for ix in range(begin_x, end_x):
                    for iy in range(begin_y, end_y):
                        painter.drawPoint(QtCore.QPointF(step_x * ix + x0, step_y * iy + y0))

    def get_positions(self):
        positions = []
        x0, y0, width, height, step_x, step_y, end_x, end_y, begin_x, begin_y, rotation = self.map_area_parameters()
        if (step_x > 0 and step_y > 0):
            nx = end_x - begin_x
            ny = end_y - begin_y
            if nx * ny <= 1000000:
                for ix in range(begin_x, end_x):
                    for iy in range(begin_y, end_y):
                        x = step_x * ix + x0
                        y = step_y * iy + y0
                        global_x = self.get_parameter("x") + x * math.cos(math.radians(rotation)) - y * math.sin(math.radians(rotation))
                        global_y = self.get_parameter("y") + y * math.cos(math.radians(rotation)) + x * math.sin(math.radians(rotation))
                        positions.append((global_x, global_y))
        return positions


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


        layout = QtWidgets.QVBoxLayout() # main vertical layout
        self.setLayout(layout)
        hlayout1 = QtWidgets.QHBoxLayout() # horizontal layout for graphics view and mapping
        layout.addLayout(hlayout1)
        self.viewwidget = ZoomableGraphicsView()
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

    def update_label_total_map_count(self):
        points = []
        for map_area in self.map_area_items:
            points += map_area.get_positions()
        order_function =  lambda p: p[0] * 100 * numpy.pi + p[1]
        points.sort(key = order_function) # low probability of equal points
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

        self.label_total_map_count.setText(str(len(unique)) + " points total.")

    def add_map_area(self):
        if len(self.map_area_items) == 0:
            self.button_delete_map_area.setEnabled(True)
        map_area = MapAreaItem(self)
        self.map_area_layout.removeItem(self.map_area_layout.itemAt(\
            self.map_area_layout.count() - 1))
        self.map_area_layout.insertWidget(-3, map_area.widget)
        self.map_area_layout.addStretch(10)
        self.map_area_items.append(map_area)

    def delete_map_area(self):
        if len(self.map_area_items) == 1:
            self.button_delete_map_area.setEnabled(False)
        self.scene.removeItem(self.map_area_items[-1])
        self.map_area_items[-1].widget.setVisible(False)
        self.map_area_layout.removeWidget(self.map_area_items[-1].widget)
        self.map_area_items.pop(-1)

    def loadSettings(self):
        try:
            with open("config\\map_widget.cfg", "r") as file:
                axes = jsonpickle.decode(file.read())
                for direction in axes:
                    self.combos[direction].setCurrentText(axes[direction])

        except Exception as e:
            self.saveSettings()
            print(e)

    def saveSettings(self):
        try:
            with open("config\\map_widget.cfg", "w") as file:
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
            for direction, combo in self.combos.items():
                if combo.currentText() == "None":
                    return
                device_id = combo.currentIndex() - 1
                # print(self.pools[device_id][0])
                if direction == "x":
                    self.cursor.setX(self.pools[device_id][1]())
                else:
                    self.cursor.setY(self.pools[device_id][1]())


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    okno = MapWidget([])
    sys.exit(app.exec_())