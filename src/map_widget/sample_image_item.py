from scipy import optimize
from PyQt5 import QtWidgets, QtGui, QtCore, QtSvg
from collections import OrderedDict
import jsonpickle

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
            self.parentItem().removeAnchor(self, save = True)


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
        button_fit.clicked.connect(self.findBestTransform)

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
            edit.editingFinished.connect(self.saveSettings)
            self.edits[s] = edit

            check = QtWidgets.QCheckBox("Fit")
            layout.addWidget(check, 0, 2 * col)
            self.checks[s] = check

            col += 1

        for i in ["x", "y", "width", "rotation"]:
            self.checks[i].setChecked(1)

        self.last_directory = ""
        try:
            with open("config" + os.sep + "map_widget_image_dir.cfg", "r") as file:
                self.last_directory= jsonpickle.decode(file.read())
        except Exception as e:
            print(e)


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
                self.saveSettings()

    def loadImage(self):
        self.pixmap = QtGui.QPixmap()
        fileName = QtWidgets.QFileDialog.getOpenFileName(self.parent, "Load sample image",
                                                         self.last_directory, "Image Files (*.png *.jpg *.bmp *.svg)")
        fileName = fileName[0]
        self.last_directory = '/'.join(fileName.split('/')[:-1])
        try:
            with open("config" + os.sep + "map_widget_image_dir.cfg", "w") as file:
                file.write(jsonpickle.encode(self.last_directory))
        except Exception as e:
            print(e)

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
            self.loadSettings()
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

    def loadSettings(self):
        try:
            with open(self.config_filename, "r") as file:
                transform_params, anchors = jsonpickle.decode(file.read())

                for anchor in self.anchor_items:
                    self.removeAnchor(anchor, save = False)
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

    def saveSettings(self):
        try:
            with open(self.config_filename, "w") as file:
                anchors = [(a.real_pos, (a.pos().x(), a.pos().y())) for a in self.anchor_items]
                transform_params = [float(self.edits[key].text()) for key in list(self.sides)]
                file.write(jsonpickle.encode([transform_params, anchors]))
        except Exception as e:
            print(e)

    def removeAnchor(self, anchor_item, save = False):
        self.anchor_items.remove(anchor_item)
        anchor_item.setParentItem(None)
        anchor_item.scene().removeItem(anchor_item)
        if save:
            self.saveSettings()

    def findBestTransform(self):
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

        def updateTransformParams(params):
            j = 0
            for i in free_params_index:
                transform_params[i] = params[j]
                j += 1

        def buildTransform(params):
            updateTransformParams(params)
            transform = QtGui.QTransform()
            transform.translate(transform_params[0], transform_params[1])
            transform.rotate(transform_params[2])
            transform.scale(transform_params[3],
                            transform_params[3] / transform_params[4] / (float(self.w) / float(self.h)))
            transform.scale(1 / self.w, 1 / self.h)
            return transform

        def fitfunc(params):
            transform = buildTransform(params)
            chi2 = 0.
            for point0, point1 in data:
                diff = QtCore.QPointF(point1[0], point1[1]) - transform.map(point0)
                chi2 += diff.x() ** 2 + diff.y() ** 2
            return chi2

        best = optimize.fmin(fitfunc, free_params_initial)
        updateTransformParams(best)
        for i in range(len(keys)):
            self.edits[keys[i]].setText(str(transform_params[i]))
        self.updatePixmap()
        self.saveSettings()

