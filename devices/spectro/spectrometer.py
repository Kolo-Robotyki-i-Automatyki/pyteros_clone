# -*- coding: utf-8 -*-
"""
Spectrometer class represents a typical spectrometer, such as an OceanOptics
device, or a Czerny-Turner monochromator with a CCD.
"""

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler
from PyQt5 import QtWidgets,QtCore
import numpy as np

class SpectrometerWorker(DeviceWorker):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def init_device(self):
        pass
        
    def status(self):
        d = super().status()
        d["cooler"] = self.get_cooler_state()
        d["temperature"] = self.get_temperature()
        d["status"] = self.status()
        lambda_min,lambda_center,lambda_max = self.get_wavelength()
        d["wavelength"] = lambda_center
        exposure,num = self.get_exposure_time()
        d["exposure"] = exposure
        d["number"] = num
        return d
    
    @handler("Spectrometer", "set_cooler")
    def set_cooler(self, state):
        """ state is True or False """
        pass
    
    @handler("Spectrometer", "get_cooler_state")
    def get_cooler_state(self):
        return True
    
    @handler("Spectrometer", "get_temperature")
    def get_temperature(self):
        return np.nan
        
    @handler("Spectrometer", "set_exposure_time")
    def set_exposure(self, exp_time, number):
        pass
    
    @handler("Spectrometer", "get_exposure_time")
    def get_exposure_time(self):
        """ Returns a tuple with exposure time (in seconds) and number of 
        accumulations """
        return (0, 1)
    
    @handler("Spectrometer", "start_acquisition")
    def start_acquisition(self, continuous=False):
        pass
    
    @handler("Spectrometer", "acquisition_status")
    def acquisition_status(self):
        """ Returns one of following strings: 'running', 'idle'"""
        return 'idle'
        
    @handler("Spectrometer", "get_latest_data")
    def get_latest_data(self):
        """ Returns the last measured data either as 1D or 2D array.
        The first dimension should be the same """
        return 
    
    @handler("Spectrometer", "get_measurement_time")
    def get_measurement_time(self):
        """ Returns estimated time (in seconds) of the whole measurement.
        Usually it is close to the exposure time, but could be significantly
        longer in step&glue mode"""
        return 0
    
    @handler("Spectrometer", "set_wavelength")
    def set_wavelength(self, wavelength):
        pass
    
    @handler("Spectrometer", "get_wavelength")
    def get_wavelength(self):
        """ Returns a tuple (lambda_min, lambda_center, lambda_max)"""
        return (-10,0,10)
    
    
    
class Spectrometer(DeviceOverZeroMQ):
  
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.createDelegatedMethods("Spectrometer")
        
        
    def createDock(self, parentWidget, menu=None):
        """ Function for integration in GUI app. Implementation below 
        creates a button and a display """
        dock = QtWidgets.QDockWidget("Spectrometer", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        widget.setLayout(layout)
        
        self.display_temp = QtWidgets.QLabel()
        self.display_temp.setMaximumWidth(60)
        self.display_temp.setText("<center>Cooler: ??<br/>T = ???</center>")
        layout.addWidget(self.display_temp)
        
        vlayout = QtWidgets.QVBoxLayout()
        layout.addLayout(vlayout)
        layout2 = QtWidgets.QHBoxLayout()
        vlayout.addLayout(layout2)
        
        layout2.addWidget(QtWidgets.QLabel("Exposure:"))
        self.input_exposure = QtWidgets.QLineEdit()
        layout2.addWidget(self.input_exposure)
        
        layout2.addWidget(QtWidgets.QLabel("Number of accumulations:"))
        self.input_number = QtWidgets.QLineEdit()
        layout2.addWidget(self.input_number)
        
        layout2.addWidget(QtWidgets.QLabel("Total:"))
        self.display_time = QtWidgets.QLineEdit()
        self.display_time.setEnabled(False)
        layout2.addWidget(self.display_time)
        
        layout3 = QtWidgets.QHBoxLayout()
        vlayout.addLayout(layout3)
        layout3.addWidget(QtWidgets.QLabel("Wavelength:"))
        self.input_wavelength = QtWidgets.QLineEdit()
        layout3.addWidget(self.input_wavelength)        
        
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
            
        # Following lines "turn on" the widget operation
        #self.increaseVoltageButton.clicked.connect(lambda pressed: self.incVoltage())
        self.createListenerThread(self.updateSlot)

        
    def updateSlot(self, status):
        pass
        #self.voltageDisplay.setValue(status["voltage"])