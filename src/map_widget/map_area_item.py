
import math
from PyQt5 import QtWidgets, QtGui, QtCore
from collections import OrderedDict

epsilon = 0.000000001

class MapAreaItem(QtWidgets.QGraphicsItem):
    def __init__(self, parent, x=-100, y=200, width=200, height=150, step_x=10, step_y=10):
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
            [("x", x), ("y", y), ("width", width), ("height", height), ("rotation", 0), ("step_x", step_x), ("step_y", step_y)])
        self.edits = OrderedDict([])

        col = 1
        for s in self.sides:
            layout.addWidget(QtWidgets.QLabel(s + ":"), col, 0)
            edit = QtWidgets.QLineEdit(str(self.sides[s]))
            edit.setValidator(QtGui.QDoubleValidator())
            layout.addWidget(edit, col, 1)
            edit.setFixedWidth(70)
            edit.editingFinished.connect(self.updateTransform)
            edit.editingFinished.connect(self.scene.update)
            self.edits[s] = edit
            col += 1

        for s in self.sides:
            self.edits[s].textChanged.connect(self.updateLabelMapSize)
            self.edits[s].textChanged.connect(self.parent.updateLabelTotalMapCount)

        self.updateLabelMapSize()
        self.parent.updateLabelTotalMapCount()
        self.updateTransform()

    def setParameter(self, parameter, value):
        if value == 0:
            self.edits[parameter].setText("0")
        else:
            self.edits[parameter].setText(str(round(value, 7 - int(math.floor(math.log10(abs(value)))))))
        self.updateTransform()

    def getParameter(self, parameter):
        return float(self.edits[parameter].text())

    def updateBorderRect(self, zoom):
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
        return QtCore.QRectF(0, 0, self.getParameter("width"), self.getParameter("height"))

    def updateTransform(self):
        transform = QtGui.QTransform()
        transform.translate(self.getParameter("x"), self.getParameter("y"))
        transform.rotate(self.getParameter("rotation"))
        self.setTransform(transform)

    def hoverEnterEvent(self, event):
        self.refreshHoverRect(event.pos())

    def hoverLeaveEvent(self, event):
        self.hover = None
        self.update()
        self.scene.update()

    def hoverMoveEvent(self, event):
        self.refreshHoverRect(event.pos())

    def refreshHoverRect(self, mouse_pos):
        self.hover = None
        for rect in self.border_rect_ordered_keys:  # rectangles can overlap for small zoom, ordering prefers corners for easy resize
            if self.border_rect[rect].contains(mouse_pos):
                self.hover = rect

        self.scene.update()

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.drag = None
        self.refreshHoverRect(event.pos())
        self.drag = self.hover
        self.drag_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.refreshHoverRect(event.pos())
        self.drag = None

    def mouseMoveEvent(self, event):
        if self.drag is not None:
            flip_x = {'l': 'r', 'tl': 'tr', 't': 't', 'tr': 'tl', 'r': 'l', 'br': 'bl', 'b': 'b', 'bl': 'br'}
            flip_y = {'l': 'l', 'tl': 'bl', 't': 'b', 'tr': 'br', 'r': 'r', 'br': 'tr', 'b': 't', 'bl': 'tl'}
            v = event.pos() - self.drag_pos

            x = 0
            y = 0
            width = self.getParameter("width")
            height = self.getParameter("height")

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
            self.setParameter("x", new_pos.x())
            self.setParameter("y", new_pos.y())
            self.setParameter("width", width)
            self.setParameter("height", height)

            self.scene.update()
            self.update()

    def mapOrigin(self): #defines offset of grid of map points, in map area coordinates
        if self.parent.check_box_snap.isChecked():
            a = math.radians(self.getParameter("rotation"))
            x = self.getParameter("x")
            y = self.getParameter("y")
            return (- x * math.cos(a) - y * math.sin(a), - y * math.cos(a) + x * math.sin(a))
        else:
            return (0, 0)

    def mapAreaParameters(self):
        x0, y0 = self.mapOrigin()
        width = self.getParameter("width")
        height = self.getParameter("height")
        step_x = self.getParameter("step_x")
        step_y = self.getParameter("step_y")
        end_x = math.floor((width - x0) / step_x + epsilon + 1)
        end_y = math.floor((height - y0) / step_y + epsilon + 1)
        begin_x = math.floor((-x0) / step_x - epsilon + 1)
        begin_y = math.floor((-y0) / step_y - epsilon + 1)
        rotation = self.getParameter("rotation")
        return (x0, y0, width, height, step_x, step_y, end_x, end_y, begin_x, begin_y, rotation)

    def updateLabelMapSize(self):
        end_x, end_y, begin_x, begin_y = self.mapAreaParameters()[6:10]
        s = str(end_x - begin_x) + "x" + str(end_y - begin_y) + ", total: " + str((end_x - begin_x)*(end_y - begin_y))
        self.label_map_size.setText(s)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        zoom = option.levelOfDetailFromTransform(painter.worldTransform())

        self.updateBorderRect(zoom)

        pen = QtGui.QPen()
        pen.setCosmetic(True)  # fixed width regardless of transformations
        pen.setColor(QtGui.QColor(128, 128, 128))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())
        if self.hover is not None:
            painter.drawRect(self.border_rect[self.hover])

        max_grid = max(zoom * self.getParameter("step_x"), zoom * self.getParameter("step_y"))
        min_grid = min(zoom * self.getParameter("step_x"), zoom * self.getParameter("step_y"))
        if max_grid > 6 and min_grid > 3:

            x0, y0, width, height, step_x, step_y, end_x, end_y, begin_x, begin_y, rotation = self.mapAreaParameters()

            pen = QtGui.QPen()
            pen.setCosmetic(True)  # fixed width regardless of transformations
            pen.setColor(QtGui.QColor(255, 0, 0))
            pen.setWidth(max(2, min(7, max_grid / 5)))
            painter.setPen(pen)

            if (end_x - begin_x) * (end_y - begin_y) < 100000:
                for ix in range(begin_x, end_x):
                    for iy in range(begin_y, end_y):
                        painter.drawPoint(QtCore.QPointF(step_x * ix + x0, step_y * iy + y0))

    def getPositions(self):
        positions = []
        x0, y0, width, height, step_x, step_y, end_x, end_y, begin_x, begin_y, rotation = self.mapAreaParameters()
        if (step_x > 0 and step_y > 0):
            nx = end_x - begin_x
            ny = end_y - begin_y
            if nx * ny <= 1000000:
                for ix in range(begin_x, end_x):
                    for iy in range(begin_y, end_y):
                        x = step_x * ix + x0
                        y = step_y * iy + y0
                        global_x = self.getParameter("x") + x * math.cos(math.radians(rotation)) - y * math.sin(math.radians(rotation))
                        global_y = self.getParameter("y") + y * math.cos(math.radians(rotation)) + x * math.sin(math.radians(rotation))
                        positions.append((global_x, global_y))
        return positions
