from PyQt5 import QtWidgets,QtCore

import ctypes as ct
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler
from PyQt5 import QtWidgets,QtCore
import time

import os
os.environ["PATH"] = \
           "C:\\pyLUMS\\devices\\attocube\\" + os.pathsep + os.environ["PATH"]
attodll = ct.windll.LoadLibrary("hvpositionerv2.dll")

default_req_port = 7006
default_pub_port = 7007

class ANC350Worker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.connected = False

    def status(self):
        d = super().status()
        d["connected"] = self.connected
        for i in self.axes():
            d["axis%d_pos" % i] = self.axisPos(i)
        return d

    def init_device(self):
        if self.connected:
            return
        class positionerinfo(ct.Structure):
            _fields_ = [("id", ct.c_int32), ("locked", ct.c_bool)]
        mem = ct.POINTER(ct.POINTER(positionerinfo))()
        count = attodll.PositionerCheck(ct.byref(mem))
        if count < 1:
            return Exception("No Attocube controllers found", \
                                "No ANC350 controllers found")
        self.handle = ct.c_int32()
        ret = attodll.PositionerConnect(0, ct.byref(self.handle))
        if ret != 0:
            return Exception("Attocube:PositionerConnect", "Function failed")
        self.connected = True

        for axis in range(9):
            attodll.PositionerStopDetection(self.handle, ct.c_int32(axis), \
                                             ct.c_bool(False))
        time.sleep(0.5)
        self.axesList = []
        self.axisDirection = {}
        for axis in range(9):
            if self.axisPos(axis) != 0:
                self.axisDirection[axis] = 0
                self.axesList.append(axis)
        print("Following axes are now enabled: ", self.axes())

    @handler("ANC350", "axes")
    def axes(self):
        return self.axesList

    @handler("ANC350", "disconnect")
    def disconnect(self):
        if not self.connected:
            return
        for i in range(3):
            self.disableAxis(i)
        attodll.PositionerClose(self.handle)
        self.connected = False

    @handler("ANC350", "enableAxis")
    def enableAxis(self, axis):
        attodll.PositionerSetOutput(self.handle, ct.c_int32(axis), True)

    @handler("ANC350", "disableAxis")
    def disableAxis(self, axis):
        attodll.PositionerSetOutput(self.handle, ct.c_int32(axis), False)

    @handler("ANC350", "moveSteps")
    def moveSteps(self, axis, steps):
        """Number of steps can be positive or negative"""
        d = ct.c_int32(0 if steps > 0 else 1)
        for i in range(abs(steps)):
            self.dll.PositionerMoveSingleStep(self.handle, ct.c_int32(axis), d)
            time.sleep(0.01)

    @handler("ANC350", "moveAbsolute")
    def moveAbsolute(self, axis, target, wait=False):
        attodll.PositionerMoveAbsolute(self.handle, ct.c_int32(axis), \
                                        ct.c_int32(target*1000), ct.c_int32(0))

    @handler("ANC350", "stopMovement")
    def stopMovement(self, axis):
        attodll.PositionerStopMoving(self.handle, ct.c_int32(axis))

    @handler("ANC350", "moveVelocity")
    def moveVelocity(self, axis, frequency):
        if frequency == 0:
            self.stopMovement(axis)
            self.axisDirection[axis] = 0
            return
        if frequency < 0:
            frequency = -frequency
            dir = 1
        else:
            dir = 0
        attodll.PositionerFrequency(self.handle, ct.c_int32(axis), ct.c_int32(frequency))
        if 1 - 2 * dir != self.axisDirection[axis]:
            attodll.PositionerMoveContinuous(self.handle, ct.c_int32(axis), ct.c_int32(dir))
        self.axisDirection[axis] = 1 - 2 * dir

    @handler("ANC350", "setFrequency")
    def setFrequency(self, axis, frequency):
        attodll.PositionerFrequency(self.handle, ct.c_int32(axis), ct.c_int32(frequency))

    @handler("ANC350", "moveContinous")
    def moveContinous(self, axis, dir):
        attodll.PositionerMoveContinuous(self.handle, ct.c_int32(axis), ct.c_int32(dir))

    @handler("ANC350", "stopMovement")
    def stopMovement(self, axis):
        attodll.PositionerStopMoving(self.handle, ct.c_int32(axis))

    @handler("ANC350", "axisPos")
    def axisPos(self, axis):
        if not self.connected:
            return 0
        pos = ct.c_int32()
        attodll.PositionerGetPosition(self.handle, ct.c_int32(axis), \
                                      ct.byref(pos))
        return pos.value / 1000.

    @handler("ANC350", "axisStatus")
    def axisStatus(self, axis):
        if not self.connected:
            return 0
        status = ct.c_int32()
        attodll.PositionerGetStatus(self.handle, ct.c_int32(axis), \
                                       ct.byref(status))
        return status.value


class ANC350(DeviceOverZeroMQ):

    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.createDelegatedMethods("ANC350")

    def __del__(self):
        pass

    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Attocube ANC350", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
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
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)
        label = QtWidgets.QLabel("Axis " + str(axis))
        layout.addWidget(label)
        lineedit = QtWidgets.QLineEdit()
        layout.addWidget(lineedit)
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
            self.axis_widgets[axis][0].setText(str(status["axis%d_pos" % axis]))
            print(status["axis%d_pos" % axis])
            
            
        
if __name__ == '__main__':
    import sys
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = QtWidgets.QMainWindow()
        window.show()
        app.exec_()
    run_app()
