# -*- coding: utf-8 -*-
import scipy as sp
from scipy import optimize
import math
from PyQt5 import QtWidgets,QtGui,QtCore,QtSvg
from collections import OrderedDict
import jsonpickle


class ZoomableGraphicsView(QtWidgets.QGraphicsView):
    def __init__ (self, parent=None):
        super().__init__ (parent)
        #self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setTransform(self.transform().scale(1, -1))
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, event):
        # Zoom Factor
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor
    
        # Set Anchors
        #   self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        #self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
    
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
        self.setSceneRect(scene_rect.x() - delta.x(), scene_rect.y() - delta.y(), scene_rect.width(), scene_rect.height())
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
        circle.setRect(-5,-5,10,10)
        circle.setBrush(QtGui.QBrush(QtCore.Qt.yellow))
        circle.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self.real_pos = real_pos

    def contextMenuEvent(self, event):
        event.accept()
        menu = QtWidgets.QMenu()
        removeAction = menu.addAction("Remove anchor point")
        selectedAction = menu.exec(event.screenPos())
        if selectedAction == removeAction:
            self.parentItem().remove_anchor(self)


class SampleImageItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, parent):
        super().__init__()

        self.parent = parent
        self.scene = self.parent.scene
        self.loaded = False
        self.anchor_items = []

        self.hlayout = QtWidgets.QGridLayout()
        button_load = QtWidgets.QPushButton("Load image")
        self.hlayout.addWidget(button_load, 0, 0)
        button_load.clicked.connect(self.loadImage)

        button_fit = QtWidgets.QPushButton("Fit Transform")
        self.hlayout.addWidget(button_fit, 1, 0)
        button_fit.clicked.connect(self.find_best_transform)

        self.sides = OrderedDict([("x", -100), ("y", 100), ("rotation", 0), ("width", 100), ("aspect ratio", 1)])
        self.edits = OrderedDict([])
        self.checks = OrderedDict([])
        col = 1
        for s in self.sides:
            self.hlayout.addWidget(QtWidgets.QLabel(s + ":"), 0, 2 * col - 1)

            edit = QtWidgets.QLineEdit(str(self.sides[s]))
            edit.setValidator(QtGui.QDoubleValidator())
            self.hlayout.addWidget(edit, 1, 2 * col-1, 1 ,2)
            edit.setFixedWidth(120)
            edit.editingFinished.connect(self.updatePixmap)
            edit.editingFinished.connect(self.save_settings)
            self.edits[s] = edit

            check = QtWidgets.QCheckBox("Fit")
            self.hlayout.addWidget(check, 0, 2 * col)
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
            buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
            buttonBox.accepted.connect(dialog.accept)
            buttonBox.rejected.connect(dialog.reject)
            layout.addRow(buttonBox)
            
            #d.setWindowModality(Qt.ApplicationModal)
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
            del(self.pixmap)
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
            transform.scale(transform_params[3], transform_params[3] / transform_params[4] / (float(self.w)/float(self.h)))
            transform.scale(1 / self.w, 1 / self.h)
            self.setTransform(transform)

    def load_settings(self):
        try:
            with open(self.config_filename, "r") as file:
                transform_params, anchors = jsonpickle.decode(file.read())

                for anchor in self.anchor_items:
                    self.remove_anchor(anchor)
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


    def remove_anchor(self, anchor_item):
        self.anchor_items.remove(anchor_item)
        anchor_item.setParentItem(None)
        anchor_item.scene().removeItem(anchor_item)
        self.save_settings()
        
    def find_best_transform(self):
        """ Use least squares method to find the best transform which fits the anchor points"""
        if len(self.anchor_items) < 1:
            return

        keys = list(self.sides)
        transform_params = [float(self.edits[key].text()) for key in keys]
        free_params_index = [] # indexes of free params
        free_params_initial = []
        for i in range(len(keys)): # take at most first 2*n free parameters when there are n anchors
            if self.checks[keys[i]].isChecked() and len(free_params_index) < 2 * len(self.anchor_items):
                free_params_index.append(i)
                free_params_initial.append(transform_params[i])
        #print("init params ", free_params_initial, " free_params_index ", free_params_index)
        data = [(a.pos(),a.real_pos) for a in self.anchor_items]

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
            transform.scale(transform_params[3], transform_params[3] / transform_params[4] / (float(self.w) / float(self.h)))
            transform.scale(1 / self.w, 1 / self.h)
            return transform
        
        def fitfunc(params):
            transform = build_transform(params)
            chi2 = 0.
            for point0, point1 in data:
                diff = QtCore.QPointF(point1[0], point1[1]) - transform.map(point0)
                chi2 += diff.x()**2 + diff.y()**2
            return chi2

        best = optimize.fmin(fitfunc, free_params_initial)
        update_transform_params(best)
        for i in range(len(keys)):
            self.edits[keys[i]].setText(str(transform_params[i]))
        self.updatePixmap()
        self.save_settings()

epsilon = 0.0000000001

class MapArea(QtWidgets.QGraphicsItem):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.scene = parent.scene
        self.setZValue(10)
        self.x = 100.
        self.y = 200.
        self.width = 300.
        self.height = 400.
        self.step_x = 10.
        self.step_y = 10.
        self.scene.addItem(self)

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        zoom = option.levelOfDetailFromTransform(painter.worldTransform())

        pen = QtGui.QPen()
        pen.setCosmetic(True)  # fixed width regardless of transformations
        pen.setColor(QtGui.QColor(128, 128, 128))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())

        max_grid = max(zoom * self.step_x, zoom * self.step_y)
        if max_grid > 5:
            pen = QtGui.QPen()
            pen.setCosmetic(True)  # fixed width regardless of transformations
            pen.setColor(QtGui.QColor(255, 0, 0))
            pen.setWidth(max(2, min(7, max_grid / 5)))
            painter.setPen(pen)

            #calculate which area of map rectangle is visible on screen
            visible_rect = self.parent.viewwidget.mapToScene(self.parent.viewwidget.viewport().geometry()).boundingRect()
            x1 = max(visible_rect.x() - self.x, 0)
            x2 = min(visible_rect.x() + visible_rect.width() - self.x, self.width)
            y1 = max(visible_rect.y() - self.y, 0)
            y2 = min(visible_rect.y() + visible_rect.height() - self.y, self.height)
            #print([x1,x2,y1,y2])

            for ix in range(int(x1 / self.step_x - epsilon + 1), int(x2 / self.step_x + epsilon) + 1):
                for iy in range(int(y1 / self.step_y - epsilon + 1), int(y2 / self.step_y + epsilon) + 1):
                    painter.drawPoint(QtCore.QPointF(self.step_x * ix, self.step_y * iy))

        transform = QtGui.QTransform()
        transform.translate(self.x, self.y)
        self.setTransform(transform)

    def get_positions(self):
        positions = []
        if(self.step_x > 0 and self.step_y > 0):
            n_x = int(self.width / self.step_x + epsilon + 1)
            n_y = int(self.height / self.step_y + epsilon + 1)
            if n_x * n_y <= 1000000:
                for ix in range(n_x):
                    for iy in range(n_y):
                        positions.append((self.x + self.step_x * ix, self.y + self.step_y * iy))
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
        
        #self.resize(500, 700)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.viewwidget = ZoomableGraphicsView()
        layout.addWidget(self.viewwidget)
        
        hlayout = QtWidgets.QHBoxLayout()       
        hlayout.addWidget(QtWidgets.QLabel("x:"))
        self.xwidget = QtWidgets.QLineEdit()
        self.xwidget.setEnabled(False)
        hlayout.addWidget(self.xwidget)
        hlayout.addSpacing(20)
        hlayout.addWidget(QtWidgets.QLabel("y:"))
        self.ywidget = QtWidgets.QLineEdit()
        self.ywidget.setEnabled(False)
        hlayout.addWidget(self.ywidget)
        hlayout.addStretch(10)        
        layout.addLayout(hlayout)
        self.show()
        
        self.pixmapItem = None

        self.setupScene()

        layout.addLayout(self.bg_item.hlayout)

        hlayout3 = QtWidgets.QHBoxLayout()
        self.combos = {}
        for direction in ("x", "y"):
            hlayout3.addWidget(QtWidgets.QLabel(direction+ ":"))
            combo = QtWidgets.QComboBox()
            combo.addItem("None")
            combo.setMinimumWidth(200)
            hlayout3.addWidget(combo)
            self.combos[direction] = combo
            hlayout3.addSpacing(20)
        hlayout3.addStretch(5)
        layout.addLayout(hlayout3)
            
        buttonlayout = QtWidgets.QHBoxLayout()
        self.refreshButton = QtWidgets.QPushButton("Refresh")
        self.refreshButton.clicked.connect(self.refreshCombos)
        buttonlayout.addWidget(self.refreshButton)      
        self.startButton = QtWidgets.QPushButton("Start control")
        self.startButton.setCheckable(True)
        self.startButton.clicked.connect(self.start)
        self.startButton.clicked.connect(self.saveSettings)
        buttonlayout.addWidget(self.startButton)
        buttonlayout.addStretch(1)
        layout.addLayout(buttonlayout)

    def loadSettings(self):
        try:
            with open("config\\map_widget.cfg", "r") as file:
                axes = jsonpickle.decode(file.read())
                for direction in axes:
                    self.combos[direction].setCurrentText(axes[direction])

        except Exception as e:
            print(e)

    def saveSettings(self):
        try:
            with open("config\\map_widget.cfg", "w") as file:
                axes = {direction : self.combos[direction].currentText() for direction in self.combos}
                file.write(jsonpickle.encode(axes))
        except Exception as e:
            print(e)


    def setupScene(self):
        self.scene = QtWidgets.QGraphicsScene()
        self.viewwidget.setScene(self.scene)
        
        self.cursor = QtWidgets.QGraphicsItemGroup()
        self.cursor.setZValue(100)
        circle = QtWidgets.QGraphicsEllipseItem(self.cursor)
        circle.setRect(-5,-5,10,10)
        circle.setBrush(QtGui.QBrush(QtCore.Qt.red))
        circle.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self.scene.addItem(self.cursor)
        
        def onMouseMoveEvent(event):
            position = QtCore.QPointF(event.scenePos())
            self.xwidget.setText(str(position.x()))
            self.ywidget.setText(str(position.y()))
            
        self.scene.mouseMoveEvent = onMouseMoveEvent
        
        self.bg_item = SampleImageItem(self)

        self.maparea = MapArea(self)
        

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
                    self.pools.append( _create_apt_poll(apt, name, serial) )
        except Exception as e:
            print(e)

        try:
            from devices.attocube.anc350 import ANC350
            for name, anc350 in {k: v for k, v in self.device_list.items() if isinstance(v, ANC350)}.items():
                for axis in anc350.axes():
                    self.pools.append(_create_anc350_poll(anc350, name, axis))
        except Exception as e:
            print(e)
        
        for direction ,combo in self.combos.items():
            n = combo.currentIndex()
            combo.clear()
            combo.addItem("None", lambda : None)
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
                #print(self.pools[device_id][0])
                if direction == "x":
                    self.cursor.setX(self.pools[device_id][1]())
                else:
                    self.cursor.setY(self.pools[device_id][1]())


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    okno = MapWidget([])
    sys.exit(app.exec_())