from PyQt5 import QtWidgets,QtCore

import ctypes as ct
import time
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler

import os
os.environ["PATH"] = \
           "C:\\pyLUMS\\devices\\attocube\\" + os.pathsep + os.environ["PATH"]
attodll = ct.windll.LoadLibrary("hvpositionerv2.dll")


class ANC350Worker(DeviceWorker):
    def __init__(self, *args, **kwargs):        
        super().__init__(*args, **kwargs)
        self.connected = False
        
    def status(self):
        d = super().status()
        d["connected"] = self.connected
        for i in range(3):
            d["axis%d_pos" % i] = self.axisPos(i)
        return d
    
    @handler("ANC350", "connect")
    def connect(self):
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
        ret = attodll.PositionerConnect(0,ct.byref(self.handle))
        if ret != 0:
            return Exception("Attocube:PositionerConnect", "Function failed")
        self.connected = True
        for axis in range(3):
            self.enableAxis(axis)
            attodll.PositionerStopDetection(self.handle,ct.c_int32(axis), \
                                             ct.c_bool(False))
    
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
        
    def moveSteps(self, axis, steps):
        """Number of steps can be positive or negative"""
        d = ct.c_int32(0 if steps>0 else 1)
        for i in range(abs(steps)):
            self.dll.PositionerMoveSingleStep(self.handle, ct.c_int32(axis), d)
            time.sleep(0.01)
            
    @handler("ANC350", "moveAbsolute")
    def moveAbsolute(self, axis, target, wait=False):
        attodll.PositionerMoveAbsolute(self.handle, ct.c_int32(axis), \
                                        ct.c_int32(target*1000), ct.c_int32(0))
    
    @handler("ANC350", "stopMovement")
    def stopMovement(self, axis):
        attodll.PositionerStopMoving(self.handle,ct.c_int32(axis))
    
    @handler("ANC350", "axisPos")
    def axisPos(self, axis):
        if not self.connected:
            return 0
        pos = ct.c_int32()
        attodll.PositionerGetPosition(self.handle,ct.c_int32(axis), \
                                       ct.byref(pos))
        return pos.value / 1000.



class ANC350(DeviceOverZeroMQ):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.createDelegatedMethods("ANC350")
        
    
    def __del__(self):
        pass
    
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
    
    def createWidgetForAxis(self, layout, axis):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)
        label = QtWidgets.QLabel("Axis "+str(axis))
        layout.addWidget(label)
        lineedit = QtWidgets.QLineEdit()
        layout.addWidget(lineedit)
        return (lineedit,)
        
    
    
    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Attocube ANC350", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        widget.setLayout(layout)
        
        self.connectButton = QtWidgets.QPushButton("Connect", parentWidget)
        self.connectButton.setCheckable(True)
        def onButtonToggled(state):
            if state:
                self.connectToDevice()
            else:
                self.disconnectFromDevice()
        self.connectButton.toggled.connect(onButtonToggled)
        layout.addWidget(self.connectButton)
        
        axis_widgets = {axis: self.createWidgetForAxis(layout,axis) 
                                                    for axis in range(3)}
        
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
        
        def updateSlot(status):
            for axis in axis_widgets:
                axis_widgets[axis][0].setValue(status["axis%d_pos" % axis])
                print(status["axis%d_pos" % axis])
        
        self.createListenerThread(self.updateSlot)
            
            
        
if __name__ == '__main__':
    import sys
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = QtWidgets.QMainWindow()
        window.show()
        app.exec_()
    run_app()
