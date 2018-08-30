# -*- coding: utf-8 -*-
"""
"""

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets,QtCore
import numpy as np
import time

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
    def __init__(self, *args, port='usb', meter_index=0, **kwargs):
        '''Port specifies the interface, e.g. 'usb', 'COM1', 'gpib' '''
        super().__init__(*args, **kwargs)
        if port.lower() in ('usb','gpib'):
            self.interface = port.lower()
            self.meter_index = meter_index
        else:
            self.interface = 'rs232'
            self.portname = port
            
    unit = "W"
            
    def init_device(self):
        if self.interface == 'rs232':
            import serial
            self.ser = serial.Serial(self.portname, baudrate=19200)
        else:
            import devices.laser.LabMaxLowLevelControl as LM
            import win32com
            self.ctl = win32com.client.Dispatch(LM.CLabMaxLowLevCtl.CLSID)
            self.ctl.Initialize()
            self.ctl.CommunicationMode = LM.constants.COM_MODE_USB
            ret = self.ctl.ConnectToMeter(self.meter_index)
            if ret == 1:
                print("Probably OK")
            else:
                print("Probably not OK")
           
        self.send_command("CONF:REAT:CONT LAST")
        self.send_command("ABOR")
        self.send_command("INIT")
        
    def deinit_device(self):
        self.ctl.DeInitialize()
        
    def send_command(self, cmd):
        if self.interface == 'rs232':
            query = cmd.endswith('?')
            cmd += '\n'
            self.ser.write(cmd.encode('ascii'))
            if query:
                return self.ser.readline().decode('ascii').strip()
        else:
            self.ctl.SendCommandOrQuery(self.meter_index, cmd)
            time.sleep(0.03)
            return self.ctl.GetNextString(self.meter_index)
    
    def get_power(self):
        try:
            ret = self.send_command("FETC:ALL?")
            return float(ret.split(',')[0])
        except:
            return np.nan
        
    def get_wavelength(self):
        try:
            ret = self.send_command('CONF:WAVE:WAVE?')
            return float(ret)
        except:
            return np.nan


def _factor_W(s):
    if s == 'mW':
        return 1e-3
    elif s == "µW":
        return 1e-6
    elif s == "nW":
        return 1e-9
    else:
        return 1

    
@include_remote_methods(PowermeterWorker)
class Powermeter(DeviceOverZeroMQ):      
    unit = "mW"
      
    
    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Powermeter", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        
        layout = QtWidgets.QHBoxLayout()
        widget.setLayout(layout)
        
        self.display_power = QtWidgets.QLineEdit()
        self.display_power.setReadOnly(True)
        self.display_power.setMinimumWidth(120)
        self.display_power.setMaximumWidth(120)
        self.display_power.setAlignment(QtCore.Qt.AlignRight)
        self.display_power.mousePressEvent = self._pick_unit
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
        
        
    def _pick_unit(self, event):
        dialog = QtWidgets.QDialog(self.display_power)
        dialog.setWindowTitle("Select unit")
        layout = QtWidgets.QVBoxLayout(dialog)
        dialog.setLayout(layout)
        options = ("W", "mW", "µW", "nW")
        buttons = [QtWidgets.QRadioButton(txt, dialog) for txt in options]
        for button in buttons:
            layout.addWidget(button)
            if button.text() == self.unit:
                button.setChecked(True)
        layout.addStretch()
        buttonBox = QtWidgets.QDialogButtonBox(dialog)
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(dialog.accept)
        buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(buttonBox)
        dialog.setModal(True)
        dialog.show()
        if dialog.exec_():
            for button in buttons:
                if button.isChecked():
                    self.unit = button.text()
        
        
    def updateSlot(self, status):
        scaled = status["power"] /_factor_W(self.unit) * _factor_W(status["unit"])
        self.display_power.setText("%.1f %s" % (scaled, self.unit))