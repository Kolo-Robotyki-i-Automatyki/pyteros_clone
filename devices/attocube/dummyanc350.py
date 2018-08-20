from PyQt5 import QtWidgets,QtCore

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler
from PyQt5 import QtWidgets, QtCore, QtGui
import time

import os

NO_OF_AXES = 4

default_req_port = 7016
default_pub_port = 7017

class DummyANC350Worker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        self.rate = 0.04
        super().__init__(req_port=req_port, pub_port=pub_port, refresh_rate = self.rate)
        self.connected = False

    def loop(self):
        for i in range(NO_OF_AXES):
            self.position[i] += 0.04 * self.frequency[i] * self.moving[i] * self.direction[i]

    def status(self):
        self.loop()
        d = super().status()
        d["connected"] = self.connected
        for i in self.axes():
            d["axis%d_pos" % i] = self.axisPos(i)
        return d

    def init_device(self):
        print("init_device")
        #self.timer = QtCore.QTimer()
        #self.timer.setInterval(50)
        #self.timer.timeout.connect(self.loop)
        #self.timer.start()
        if self.connected:
            return
        self.connected = True
        self.position = [2000, 2000, 2000, 2000]
        self.frequency = [0, 0, 0, 0]
        self.direction = [1, 1, 1, 1]
        self.moving = [0, 0, 0, 0]
        self.axesList = [0, 1, 2, 3]
        print("Following dummy axes are now enabled: ", self.axes())

    @handler("DummyANC350", "axes")
    def axes(self):
        return self.axesList

    @handler("DummyANC350", "disconnect")
    def disconnect(self):
        return 1

    @handler("DummyANC350", "enableAxis")
    def enableAxis(self, axis):
        return 1

    @handler("DummyANC350", "disableAxis")
    def disableAxis(self, axis):
        return 1

    @handler("DummyANC350", "moveSteps")
    def moveSteps(self, axis, steps):
        """Number of steps can be positive or negative"""
        s = 1 if steps > 0 else -1
        for i in range(abs(steps)):
            self.position[axis] += 0.63 * s
            time.sleep(0.01)

    @handler("DummyANC350", "moveAbsolute")
    def moveAbsolute(self, axis, target, wait=False):
        self.position[axis] = target
        self.moving[axis] = 0

    @handler("DummyANC350", "stopMovement")
    def stopMovement(self, axis):
        self.moving[axis] = 0

    @handler("DummyANC350", "moveVelocity")
    def moveVelocity(self, axis, frequency):
        if frequency == 0:
            self.stopMovement(axis)
            return
        if frequency < 0:
            frequency = -frequency
            self.direction[axis] = -1
        else:
            self.direction[axis] = 1
        self.setFrequency(axis, frequency)
        self.moving[axis] = 1

    @handler("DummyANC350", "setFrequency")
    def setFrequency(self, axis, frequency):
        self.frequency[axis] = frequency

    @handler("DummyANC350", "moveContinous")
    def moveContinous(self, axis, dir):
        self.direction[axis] = 1 - 2 * dir
        self.moving[axis] = 1

    @handler("DummyANC350", "stopMovement")
    def stopMovement(self, axis):
        self.moving[axis] = 0

    @handler("DummyANC350", "axisPos")
    def axisPos(self, axis):
        return self.position[axis]

    @handler("DummyANC350", "axisStatus")
    def axisStatus(self, axis):
        return 1


class DummyANC350(DeviceOverZeroMQ):

    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.createDelegatedMethods("DummyANC350")

    def __del__(self):
        pass

    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Attocube ANC350", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QVBoxLayout(parentWidget)
        layout.setSpacing(2)
        widget.setLayout(layout)

        '''
        self.connectButton = QtWidgets.QPushButton("Connect", parentWidget)
        self.connectButton.setCheckable(True)

        def onButtonToggled(state):
            if state:
                self.connectToDevice()
            else:
                self.disconnectFromDevice()

        self.connectButton.toggled.connect(onButtonToggled)
        layout.addWidget(self.connectButton)
        '''
        self.axis_widgets = {axis: self.createWidgetForAxis(layout, axis)
                        for axis in self.axes()}

        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())

        self.createListenerThread(self.updateSlot)

    def createWidgetForAxis(self, layout, axis):
        hLayout = QtWidgets.QHBoxLayout(layout.parent())
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)
        label = QtWidgets.QLabel("Axis " + str(axis))
        hLayout.addWidget(label)
        lineedit = QtWidgets.QLineEdit()
        hLayout.addWidget(lineedit)
        layout.addLayout(hLayout)
        return (lineedit,)

    def connectToDevice(self):
        self.connectButton.setText("Connecting")
        self.connectButton.setChecked(True)
        try:
            self.connect()
            self.connectButton.setText("Connected")
            self.connectButton.setChecked(True)
        except:
            self.disconnectFromDevice()

    def disconnectFromDevice(self):
        try:
            self.connectButton.setText("Connect")
            self.connectButton.setChecked(False)
            self.disconnect()
        except:
            pass

    def updateSlot(self, status):
        for axis in self.axis_widgets:
            self.axis_widgets[axis][0].setText("%4.2f" % status["axis%d_pos" % axis])
            #print(status["axis%d_pos" % axis])
            
            
        
if __name__ == '__main__':
    import sys
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = QtWidgets.QMainWindow()
        window.show()
        app.exec_()
    run_app()
