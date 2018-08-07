# -*- coding: utf-8 -*-
import scipy as sp
from scipy import optimize
from PyQt5 import QtWidgets,QtGui,QtCore,QtSvg



class ZoomableGraphicsView(QtWidgets.QGraphicsView):
    def __init__ (self, parent=None):
        super().__init__ (parent)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

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
    def __init__(self, pixmap):
        super().__init__(pixmap)       
        self.setEnabled(True)
        self.setActive(True)
        self.setAcceptedMouseButtons(QtCore.Qt.RightButton)
        self.current_coordinates = (0, 0)
        self.anchor_items = []
    
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
            x_input = QtWidgets.QLineEdit("0.") #TODO: z current_coordinates
            layout.addRow("X coordinate", x_input)
            y_input = QtWidgets.QLineEdit("0.") #TODO: z current_coordinates
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
        
    def remove_anchor(self, anchor_item):
        self.anchor_items.remove(anchor_item)
        anchor_item.setParentItem(None)
        anchor_item.scene().removeItem(anchor_item)
        
    def find_best_transform(self):
        """ Use least squares method to find the best transform which fits the anchor points"""
        if len(self.anchor_items) < 1:
            return
        data = [(a.pos(),a.real_pos) for a in self.anchor_items]
        def build_transform(params):
            transform = QtGui.QTransform()
            if len(params >= 2):
                transform.translate(params[0], params[1])
            if len(params >= 3):
                transform.rotate(params[3])
            if len(params >= 5):
                transform.scale(params[4],params[5])
            return transform
        
        def fitfunc(params):
            transform = build_transform(params)
            chi2 = 0.
            for point0,point1 in data:
                diff = point1 - transform.map(point0)
                chi2 += diff.x()**2 + diff.y()**2
            return chi2
        
        best = optimize.fmin(fitfunc, [1,1])
        print(best)
        self.setTransform(build_transform(best))



class MapWidget(QtWidgets.QWidget):
    def __init__(self, device_list, parent=None):
        super().__init__(parent)
        self.device_list = device_list
        self.slaves = []
        self.pools = []
        self.bg_item = None
        
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.timeout)
        self.timer.start()
        self.active = False
        
        self.resize(500, 500)
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
        hlayout2 = QtWidgets.QHBoxLayout()
        button = QtWidgets.QPushButton("Load image")
        hlayout2.addWidget(button)
        button.clicked.connect(self.loadImage)
        
        sides = {"x": -100, "y": 100, "width": -100, "height": 100}
        self.edits = {}
        for s in sides:
            hlayout2.addWidget(QtWidgets.QLabel(s +":"))
            edit = QtWidgets.QLineEdit( str(sides[s]) )
            edit.setValidator(QtGui.QDoubleValidator())
            hlayout2.addWidget(edit)
            hlayout2.addSpacing(20)
            edit.editingFinished.connect(self.updatePixmap)
            self.edits[s] = edit
        hlayout2.addStretch(5) 
        layout.addLayout(hlayout2)

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
        buttonlayout.addWidget(self.startButton)
        buttonlayout.addStretch(1)
        layout.addLayout(buttonlayout)

        self.setupScene()


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
        
        self.bg_item = None
        
        pixmap = QtGui.QPixmap()
        
    def loadImage(self):
        fileName = QtWidgets.QFileDialog.getOpenFileName(self, "Load sample image", 
                                    "", "Image Files (*.png *.jpg *.bmp *.svg)")
        fileName = fileName[0]
        if not fileName:
            return

        if self.bg_item:
            self.scene.removeItem(self.bg_item)
            del(self.bg_item)
            self.bg_item = None
        try:
            if fileName.lower().endswith("svg"):
                self.bg_item = QtSvg.QGraphicsSvgItem(fileName)
            else:
                print("case2")
                pixmap = QtGui.QPixmap(fileName)
                self.bg_item = SampleImageItem(pixmap)
            self.scene.addItem(self.bg_item)
            self.updatePixmap()
        except Exception as e:
            print("Error: ", str(e))
            self.bg_item = None
    
    def updatePixmap(self):
        if self.bg_item:
            x = float(self.edits["x"].text())
            y = float(self.edits["y"].text())
            w = float(self.edits["width"].text())
            h = float(self.edits["height"].text())
            self.bg_item.resetTransform()
            rect = self.bg_item.boundingRect()
            translation = QtGui.QTransform.fromTranslate(x, y)
            self.bg_item.setTransform(translation)
            scaling = QtGui.QTransform.fromScale(w/rect.width(), h/rect.height())
            self.bg_item.setTransform(scaling, True)
            
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
            
            
    def timeout(self):
        if self.active:
            for direction, combo in self.combos.items():
                if combo.currentText() == "None":
                    return
                device_id = combo.currentIndex() - 1
                print(self.pools[device_id][1])
                if direction == "x":
                    self.cursor.setX(self.pools[device_id][1]())
                else:
                    self.cursor.setY(self.pools[device_id][1]())


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    okno = MapWidget([])
    sys.exit(app.exec_())