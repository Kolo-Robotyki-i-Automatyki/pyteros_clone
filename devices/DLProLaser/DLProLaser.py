# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets,QtCore
import TMCL
import toptica.lasersdk.client as top

default_req_port  = 7123
default_pub_port = 7124

class DLProWorker(DeviceWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def init_device(self):
        import serial
        
        self.ser = serial.Serial('COM16', 9600, timeout=5)  #opens serial port COM16
        
    def __del__(self):
        self.ser.close() #serial port close
        
    def status(self):
        """ This function will be called periodically to monitor the state 
        of the device. It should return a dictionary describing the current
        state of the device. This dictionary will be delivered to the 
        front-end class."""
        d = super().status()
        d["connected"] = True
        print(d)
        return d
    
    @remote
    def DLserial(self):
        with top.Client(top.NetworkConnection('10.96.1.233')) as client:
            return client.get('serial-number',str)
    
    
    @remote
    def motorposition(self):
        
        bus = TMCL.connect(self.ser)
        module = bus.get_module(1)
        motor = module.get_motor(2)
        return motor.axis.actual_position

@include_remote_methods(DLProWorker)
class DLPro(DeviceOverZeroMQ):  
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)	
        
    def createDock(self, parentWidget, menu = None):
        """ Function for integration in GUI app.  """
        dock = QtWidgets.QDockWidget("DLPro Laser", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        self.layout = QtWidgets.QVBoxLayout(parentWidget)
        widget.setLayout(self.layout)
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())

        self.createListenerThread(self.updateSlot)
