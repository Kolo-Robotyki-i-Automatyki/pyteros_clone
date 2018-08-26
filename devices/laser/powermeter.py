# -*- coding: utf-8 -*-
"""
"""

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets,QtCore
import numpy as np

class PowermeterWorker(DeviceWorker):
    '''Generic power meter. Subclassed for specific device'''          
    
    unit = "mW"
        
    def status(self):
        d = super().status()
        d["unit"] = self.unit
        d["power"] = self.get_power()
        d["wavelength"] = self.get_wavelength()
        return d
        
    @remote
    def get_power(self):
        '''Read out the current power'''
        return 0.
        
    @remote
    def get_wavelength(self):
        ''' Read out the wavelength setting. Irrelevant for thermal sensors '''
        return np.nan


class LabMaxWorker(PowermeterWorker):
    def __init__(self, *args, port='usb', **kwargs):
        '''Port specifies the interface, e.g. 'usb', 'COM1', 'gpib' '''
        super().__init__(*args, **kwargs)
        if port.lower() in ('usb','gpib'):
            self.interface = port.lower()
        else:
            self.interface = 'rs232'
            self.portname = port
                
    def init_device(self):
        if self.interface == 'rs232':
            import serial
            self.port = serial.Serial(self.portname, baudrate=19200)
        else:
            raise NotImplementedError("USB and GPIB transfer not implemented yet")
            
        #*IDN
        #SYSTem:STATus?
        #CONFigure:READings:CONTinuous?
        #CONFigure:READings:SEND?
        
    def send_command(self, cmd):
        query = cmd.endswith('?')
        cmd += '\n'
        res = None
        if self.interface == 'rs232':
            serial.write(cmd.encode('ascii'))
            if query:
                res = serial.readline().decode('ascii').strip()
        else:
            raise NotImplementedError("USB and GPIB transfer not implemented yet")
        return res
    
    def get_power(self):
        self.send_command("FETCh:ALL?")
        #TODO
        return 0
        
    def get_wavelength(self):
        #TODO
        self.send_command('CONF:WAVEl:WAVE?')
        return 0
    
@include_remote_methods(PowermeterWorker)
class Powermeter(DeviceOverZeroMQ):      
          
    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Powermeter", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        
        layout = QtWidgets.QHBoxLayout()
        widget.setLayout(layout)
        
        self.display_power = QtWidgets.QLineEdit()
        self.display_power.setEnabled(False)
        self.display_power.setMaximumWidth(100)
        layout.addWidget(QtWidgets.QLabel('Power:'))
        layout.addWidget(self.display_power)
        layout.addStretch()
        
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
            
        # Following lines "turn on" the widget operation
        self.createListenerThread(self.updateSlot)

        
    def updateSlot(self, status):
        self.display_power.setText("%g %s" % (status["power"],status["unit"]))