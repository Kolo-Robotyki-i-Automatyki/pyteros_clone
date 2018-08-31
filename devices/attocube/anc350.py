from PyQt5 import QtWidgets,QtCore

import ctypes as ct
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from devices import Parameter
from PyQt5 import QtWidgets, QtCore, QtGui
import time

import os
os.environ["PATH"] = \
           "C:\\pyLUMS\\devices\\attocube\\" + os.pathsep + os.environ["PATH"]

default_req_port = 7006
default_pub_port = 7007


class AttocubeAxisParameter(Parameter):
    def __init__(self, anc350, axis):
        self.anc350 = anc350
        self.axis = axis
        
    def name(self):
        return "Attocube ANC350 axis: %d" % self.axis
    
    def value(self):
        return self.anc350.axisPos(self.axis)
    
    def move_to_target(self, target):
        self.anc350.ax(self.motor_serial, target)
    
    def move_continuous(self, rate):
        self.anc350.moveVelocity(self.axis, int(rate*500))
    
    def is_moving(self):
        raise NotImplementedError


class ANC350Worker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.connected = False
        self.axesList = []
        self.axisDirection = {}

    def status(self):
        d = super().status()
        d["connected"] = self.connected
        for i in self.axes():
            d["axis%d_pos" % i] = self.axisPos(i)
        return d

    def init_device(self):
        self.dll = ct.windll.LoadLibrary("hvpositionerv2.dll")
        if self.connected:
            return
        class positionerinfo(ct.Structure):
            _fields_ = [("id", ct.c_int32), ("locked", ct.c_bool)]
        mem = ct.POINTER(ct.POINTER(positionerinfo))()
        count = self.dll.PositionerCheck(ct.byref(mem))
        if count < 1:
            return Exception("No Attocube controllers found", \
                                "No ANC350 controllers found")
        self.handle = ct.c_int32()
        ret = self.dll.PositionerConnect(0, ct.byref(self.handle))
        if ret != 0:
            return Exception("Attocube:PositionerConnect", "Function failed")
        self.connected = True

        for axis in range(9):
            self.dll.PositionerStopDetection(self.handle, ct.c_int32(axis), \
                                             ct.c_bool(False))
        time.sleep(0.5)
        for axis in range(9):
            if self.axisPos(axis) != 0:
                self.axisDirection[axis] = 0
                self.axesList.append(axis)
        print("Following axes are now enabled: ", self.axes())

    @remote
    def axes(self):
        return self.axesList

    @remote
    def disconnect(self):
        if not self.connected:
            return
        for i in range(3):
            self.disableAxis(i)
        self.dll.PositionerClose(self.handle)
        self.connected = False

    @remote
    def enableAxis(self, axis):
        self.dll.PositionerSetOutput(self.handle, ct.c_int32(axis), True)

    @remote
    def disableAxis(self, axis):
        self.dll.PositionerSetOutput(self.handle, ct.c_int32(axis), False)

    @remote
    def moveSteps(self, axis, steps):
        """Number of steps can be positive or negative"""
        d = ct.c_int32(0 if steps > 0 else 1)
        for i in range(abs(steps)):
            self.dll.PositionerMoveSingleStep(self.handle, ct.c_int32(axis), d)
            time.sleep(0.01)

    @remote
    def moveAbsolute(self, axis, target, wait=False):
        self.dll.PositionerMoveAbsolute(self.handle, ct.c_int32(axis), \
                                        ct.c_int32(target*1000), ct.c_int32(0))

    @remote
    def stopMovement(self, axis):
        self.dll.PositionerStopMoving(self.handle, ct.c_int32(axis))

    @remote
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
        self.dll.PositionerFrequency(self.handle, ct.c_int32(axis), ct.c_int32(frequency))
        if 1 - 2 * dir != self.axisDirection[axis]:
            self.dll.PositionerMoveContinuous(self.handle, ct.c_int32(axis), ct.c_int32(dir))
        self.axisDirection[axis] = 1 - 2 * dir

    @remote
    def setFrequency(self, axis, frequency):
        self.dll.PositionerFrequency(self.handle, ct.c_int32(axis), ct.c_int32(frequency))

    @remote
    def moveContinous(self, axis, dir):
        self.dll.PositionerMoveContinuous(self.handle, ct.c_int32(axis), ct.c_int32(dir))

    @remote
    def stopMovement(self, axis):
        self.dll.PositionerStopMoving(self.handle, ct.c_int32(axis))

    @remote
    def axisPos(self, axis):
        if not self.connected:
            return 0
        pos = ct.c_int32()
        self.dll.PositionerGetPosition(self.handle, ct.c_int32(axis), \
                                      ct.byref(pos))
        return pos.value / 1000.

    @remote
    def axisStatus(self, axis):
        if not self.connected:
            return 0
        status = ct.c_int32()
        self.dll.PositionerGetStatus(self.handle, ct.c_int32(axis), \
                                       ct.byref(status))
        return status.value

@include_remote_methods(ANC350Worker)
class ANC350(DeviceOverZeroMQ):

    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

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
