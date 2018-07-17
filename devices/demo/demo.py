# -*- coding: utf-8 -*-
"""

Each device is split in two parts:
    1. The worker which directly communicates with the hardware
    2. The front-end class which is accessed by the user
Communication between both parts is done by means of ZeroMQ protocol, which 
means that both parts can potentially work on different hosts.
"""

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler
from PyQt5 import QtWidgets,QtCore

class WorkerForDummyDevice(DeviceWorker):
    """ Simple stub for the class directly communicating with the hardware """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # custom initialization here
        self.voltage = 0.2
        
        
    def init_device(self):
        """ This function will be called once upon starting the process """
        print("Dummy device initialized")
        
    def status(self):
        """ This function will be called periodically to monitor the state 
        of the device. It should return a dictionary describing the current
        state of the device. This dictionary will be delivered to the 
        front-end class."""
        d = super().status()
        d["connected"] = True
        d["voltage"] = self.voltage
        print(d)
        return d
    
    @handler("Demo", "setVoltage")
    def setVoltage(self, v):
        """ Use @handler decorator for functions to expose them to the 
        front-end. For each argument you need to specify a function to convert
        it from string"""
        print("setVoltage is performed by "+str(self.__class__)+" object")
        self.voltage = v
        
    @handler("Demo", "incVoltage")
    def incVoltage(self):
        print("incVoltage is performed by "+str(self.__class__)+" object")
        self.voltage += 1
        
    @handler("Demo", "getVoltage")
    def getVoltage(self):
        print("getVoltage is performed by "+str(self.__class__)+" object")
        return self.voltage
    
    
    
    
class FrontEndForDummyDevice(DeviceOverZeroMQ):
    """ Simple stub for the class to be accessed by the user """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.createDelegatedMethods("Demo")
        
        
    def createDock(self, parentWidget, menu=None):
        """ Function for integration in GUI app. Implementation below 
        creates a button and a display """
        dock = QtWidgets.QDockWidget("Dummy device", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        widget.setLayout(layout)
        
        self.increaseVoltageButton = QtWidgets.QPushButton("Increase voltage", parentWidget)
        layout.addWidget(self.increaseVoltageButton)
        self.voltageDisplay = QtWidgets.QDoubleSpinBox(parentWidget)
        layout.addWidget(self.voltageDisplay)
        
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
            
        # Following lines "turn on" the widget operation
        self.increaseVoltageButton.clicked.connect(lambda pressed: self.incVoltage())
        self.createListenerThread(self.updateSlot)

        
    def updateSlot(self, status):
        """ This function receives periodic updates from the worker """
        self.voltageDisplay.setValue(status["voltage"])
    
    
    
def createDummyDevice():
    req_port = 5555
    pub_port = 5556
    print("Invoking worker...")
    worker = WorkerForDummyDevice(req_port=req_port, pub_port=pub_port)
    worker.start()
    print("Invoking listener...")
    frontend = FrontEndForDummyDevice(req_port=req_port, pub_port=pub_port)
    return frontend,worker

def createDummyDeviceAndWindow():
    import sys
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = QtWidgets.QMainWindow()
        
        frontend,worker = createDummyDevice()
        frontend.createDock(window)
        window.show()
        app.exec_()
    run_app()