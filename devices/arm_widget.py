
import math
from math import sin, cos
import sys
from PyQt5 import QtWidgets, QtGui, QtCore
import numpy
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt

PI = 3.14159265357
deg = PI / 180
L1 = 602.
L2 = 479.
L3 = 220.
t1 = 167.3 * deg
t2 = 129.7 * deg
b1 = 87.8 * deg
b2 = 15.0 * deg
H = 450.
size = 150
class ArmWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.a1 = 135 * deg
        self.a2 = 90 * deg
        self.a3 = 225 * deg

    def initUI(self):
        self.setFixedWidth(size)
        self.setFixedHeight(size)

        self.setWindowTitle('Arm Widget')
        self.show()

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)

        painter.setPen(QtGui.QPen(QtCore.Qt.black, 2))
        painter.fillRect(self.rect(), QtCore.Qt.white)
        sc = 0.11
        x1, y1 = (0.1*size, size - H * sc)
        x2 = x1 + sin(self.a1)*L1*sc
        y2 = y1 + cos(self.a1)*L1*sc
        x3 = x2 + sin(self.a1+self.a2-180*deg)*L2*sc
        y3 = y2 + cos(self.a1+self.a2-180*deg)*L2*sc
        x4 = x3 + sin(self.a1+self.a2+self.a3-360*deg)*L3*sc
        y4 = y3 + cos(self.a1+self.a2+self.a3-360*deg)*L3*sc

        x2t = x1 + sin(t1)*L1*sc
        y2t = y1 + cos(t1)*L1*sc
        x2b = x1 + sin(b1)*L1*sc
        y2b = y1 + cos(b1)*L1*sc

        x3t = x2 + sin(self.a1+t2-180*deg)*L2*sc
        y3t = y2 + cos(self.a1+t2-180*deg)*L2*sc
        x3b = x2 + sin(self.a1+b2-180*deg)*L2*sc
        y3b = y2 + cos(self.a1+b2-180*deg)*L2*sc

        painter.drawLine(x1,y1,x2,y2)
        painter.drawLine(x2,y2,x3,y3)
        painter.drawLine(x4,y4,x3,y3)

        painter.setPen(QtGui.QPen(QtCore.Qt.gray, 1))
        painter.drawLine(x1,y1,x2t,y2t)
        painter.drawLine(x1,y1,x2b,y2b)
        painter.drawLine(x2,y2,x3t,y3t)
        painter.drawLine(x2,y2,x3b,y3b)
        #self.drawText(event, qp)
        painter.end()

    def drawText(self, event, qp):
        qp.setPen(QtGui.QColor(168, 34, 3))
        qp.setFont(QtGui.QFont('Decorative', 10))
        qp.drawText(event.rect(), QtCore.Qt.AlignCenter, "duda")

    def set_angles(self, angles):
        self.a1 = angles[0]
        self.a2 = angles[1]
        self.a3 = angles[2]
        self.repaint()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = ArmWidget()
    sys.exit(app.exec_())