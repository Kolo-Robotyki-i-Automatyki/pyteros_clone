# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods

from PyQt5 import QtWidgets,QtCore
import TMCL
import toptica.lasersdk.client as top
from .wavemeter import Wavemeter

default_req_port = 7123
default_pub_port = 7124

class DLProWorker(DeviceWorker):
    def __init__(self, *args, wm_req_port=8123, wm_pub_port=8124, **kwargs):
        super().__init__(*args, **kwargs)
        self.wm_req_port = wm_req_port
        self.wm_pub_port = wm_pub_port
        
        
    def init_device(self):
        import serial
        self.ser = serial.Serial('COM16', 9600, timeout=5)  #opens serial port COM16
        self.wavemeter = Wavemeter(req_port=self.wm_req_port, pub_port=self.wm_pub_port)
        self.bus = TMCL.connect(self.ser)
        self.module = self.bus.get_module(1)
        self.motor = self.module.get_motor(2)
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
    def get_wavelength_from_wavemeter(self):
        return self.wavemeter.get_wavelength()
    
    @remote
    def DLget_serial(self):
        with top.Client(top.NetworkConnection('10.96.1.233')) as client:
            return client.get('serial-number',str)
    @remote
    def Dlget_current(self):
        with top.Client(top.NetworkConnection('10.96.1.233')) as client:
            return client.get('laser1:dl:cc:current-set',float)
    @remote
    def Dlset_current(self,current):
        with top.Client(top.NetworkConnection('10.96.1.233')) as client:
            client.set('laser1:dl:cc:current-set',float(current))
    @remote
    def motor_position(self):
        
        
        return self.motor.axis.actual_position
    @remote
    def motor_get_wavelength(self):
        return ((0.00013*(self.motor_position()-600000)) + 517.295)
    @remote
    def motor_set_wavelength(self, wavelength):
        
        self.motor.move_absolute(int(((wavelength-517.295) / 0.00013) + 600000))

    
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
