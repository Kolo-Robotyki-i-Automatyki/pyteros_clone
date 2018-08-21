# -*- coding: utf-8 -*-
"""
Spectrometer class represents a typical spectrometer, such as an OceanOptics
device, or a Czerny-Turner monochromator with a CCD.
"""

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
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
        d["status"] = self.acquisition_status()
        lambda_min,lambda_center,lambda_max = self.get_wavelength()
        d["wavelength"] = lambda_center
        exposure,num = self.get_exposure_time()
        d["exposure"] = exposure
        d["number"] = num
        return d
    
    @remote
    def set_cooler(self, state):
        """ state is True or False """
        pass
    
    @remote
    def get_cooler_state(self):
        return True
    
    @remote
    def get_temperature(self):
        return np.nan
        
    @remote
    def set_exposure(self, exp_time, number):
        pass
    
    @remote
    def get_exposure_time(self):
        """ Returns a tuple with exposure time (in seconds) and number of 
        accumulations """
        return (0, 1)
    
    @remote
    def start_acquisition(self, continuous=False):
        pass
    
    @remote
    def acquisition_status(self):
        """ Returns one of following strings: 'running', 'idle'"""
        return 'idle'
        
    @remote
    def get_latest_data(self):
        """ Returns the last measured data either as 1D or 2D array.
        The first dimension should be the same """
        return 
    
    @remote
    def get_measurement_time(self):
        """ Returns estimated time (in seconds) of the whole measurement.
        Usually it is close to the exposure time, but could be significantly
        longer in step&glue mode"""
        return 0
    
    @remote
    def set_wavelength(self, wavelength):
        pass
    
    @remote
    def get_wavelength(self):
        """ Returns a tuple (lambda_min, lambda_center, lambda_max)"""
        return (-10,0,10)
    
    
@include_remote_methods(SpectrometerWorker)    
class Spectrometer(DeviceOverZeroMQ):
  
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        
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
        
        self.start_button = QtWidgets.QPushButton("Start")
        layout3.addWidget(self.start_button)
        self.start_button.clicked.connect(self.start_acquisition)
        
        self.get_button = QtWidgets.QPushButton("Retrieve")
        layout3.addWidget(self.get_button)
        self.get_button.clicked.connect(self.get_latest_data)
        
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