# -*- coding: utf-8 -*-
import scipy as sp
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
        #newPos = self.mapToScene(event.pos())
    
        # Move scene to old position
        #delta = newPos - oldPos
        #self.translate(delta.x(), delta.y())


def _create_apt_poll(apt, serial):
    """Creates a pair of a name and a function to get stage position """
    func = lambda : apt.position(serial)
    return ("APT s/n: %d" % serial, func)
    

class MapWidget(QtWidgets.QWidget):
    def __init__(self, device_list, parent=None):
        super().__init__(parent)
        self.device_list = device_list
        
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(500)
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
        
        sides = {"left": -100, "right": 100, "bottom": -100, "top": 100}
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
        self.bg_item = QtWidgets.QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.bg_item)
        
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
                self.bg_item = QtWidgets.QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.bg_item)
            self.updatePixmap()
        except Exception as e:
            print("Error: ", str(e))
            self.bg_item = None
    
    def updatePixmap(self):
        if self.bg_item:
            l = float(self.edits["left"].text())
            r = float(self.edits["right"].text())
            t = float(self.edits["top"].text())
            b = float(self.edits["bottom"].text())
            self.bg_item.resetTransform()
            rect = self.bg_item.boundingRect()
            translation = QtGui.QTransform.fromTranslate(l, b)
            self.bg_item.setTransform(translation)
            scaling = QtGui.QTransform.fromScale((r-l)/rect.width(), (t-b)/rect.height())
            self.bg_item.setTransform(scaling, True)
            
    def start(self, activate=True):
        self.active = activate
            
    def refreshCombos(self):
        self.start(False)
        slaves = []
        
        try:
            from devices.thorlabs.apt import APT
            for apt in filter(lambda d: isinstance(d, APT), self.device_list):
                for serial in apt.devices():
                    slaves.append( _create_apt_poll(apt,serial) )
        except Exception as e:
            print(e)
        
        for direction,combo in self.combos.items():
            n = combo.currentIndex()
            combo.clear()
            combo.addItem("None", lambda : None)
            for name,func in slaves:
                combo.addItem(name, func)
            combo.setCurrentIndex(n)
            
            
    def timeout(self):
        if self.active:
            for direction,combo in self.combos.items():
                pos = combo.currentData()()
                if pos is None:
                    return
                if direction == "x":
                    self.cursor.setX(pos)
                else:
                    self.cursor.setY(pos)


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    okno = MapWidget([])
    sys.exit(app.exec_())