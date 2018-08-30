# -*- coding: utf-8 -*-
"""
Support for HighFinesse wavemeter.
"""

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets,QtCore
import numpy as np
import ctypes as ct
import scipy.signal


def is_single_mode(patternData):
    itemCount = len(patternData)
    peaks=scipy.signal.find_peaks(patternData, height=300, distance=50)
    amplitudes=peaks[1]
    poly2=np.polyfit(peaks[0],amplitudes['peak_heights'],2)  
    poly1=np.polyfit(np.arange(len(peaks[0])),peaks[0],1)
    fizeu=(np.polyval(poly2,np.arange(0,itemCount))/(1+(5*np.sin(np.pi*((np.arange(0,itemCount)-poly1[1])/poly1[0])))**2))
    deviation=np.mean((patternData-fizeu)**2/fizeu**2)
    return bool(deviation<0.5)

            
class WavemeterWorker(DeviceWorker):
    #constants:
    cInstNotification = 1
    cNotifyInstallCallback = 0
    cNotifyInstallCallbackEx = 4
    cNotifyRemoveCallback = 1
    cmiResultMode = 1
    cmiDLLDetach = 30
    
    def __init__(self, *args, dllpath="C:\Windows\System32\wlmData.dll", **kwargs):
        super().__init__(*args, **kwargs)
        self.dllpath = dllpath
        self.channel = 1
           
    @remote
    def is_single_mode(self):
        #itemCount=self.dll.GetPatternItemCount(ct.c_int32(1))
        #patternData=(ct.c_uint16 *int(itemCount))()
        #self.dll.GetPatternData(ct.c_int32(1), ct.byref(patternData))
        #patternData=np.array(patternData[:])-10
        #return is_single_mode(patternData)
        self.mutex.lock()
        ret = self.x_is_single_mode
        self.mutex.unlock()
        return ret
  
    def init_device(self):
        self.mutex = QtCore.QMutex()
        self.dll = ct.WinDLL(self.dllpath)
        self.dll.GetWavelengthNum.restype = ct.c_double
        self.dll.GetFrequencyNum.restype = ct.c_double
        self.dll.SetPattern(ct.c_int32(1),ct.c_int32(1))
        self.install_callback()
        self.x_wavelength = 0
        self.x_exposure = 0
        self.x_is_single_mode = False
        
    def close_device(self):
        self.remove_callback()
            
    def status(self):
        d = super().status()
        self.mutex.lock()
        d["wavelength_vac"] = self.x_wavelength
        d["wavelength_air"] = np.nan #TODO
        d["exposure"] = self.x_exposure
        d["single_mode"] = self.x_is_single_mode
        self.mutex.unlock()
        return d
            
    @remote
    def get_wavelength(self):
        self.mutex.lock()
        #self.dll.GetWavelengthNum(ct.c_long(self.channel), ct.c_double(0))
        ret = self.x_wavelength
        self.mutex.unlock()
        return ret

    #def get_frequency(self):
    #    return self.dll.GetFrequencyNum(ct.c_long(self.channel), ct.c_double(0))
    
    def install_callback(self):       
        @ct.WINFUNCTYPE(None, ct.c_int, ct.c_int, ct.c_double, ct.c_int)
        def callback(mode, intval, dblval, res1):    
            if mode == 42:
                itemCount= ct.WinDLL("C:\Windows\System32\wlmData.dll").GetPatternItemCount(ct.c_int32(1))
                patternData=(ct.c_uint16 *int(itemCount))()
                ct.WinDLL("C:\Windows\System32\wlmData.dll").GetPatternData(ct.c_int32(1), ct.byref(patternData))
                patternData=np.array(patternData[:])-10
                b = is_single_mode(patternData)
                self.mutex.lock()
                self.x_wavelength = dblval
                self.x_is_single_mode = b
                self.mutex.unlock()
            elif mode == WavemeterWorker.cmiDLLDetach: # WLM has exited
                    self.remove_callback()
                    
        self.callback_func = callback # stops garbage collector from deleting the function
        ret = self.dll.Instantiate(ct.c_int(self.cInstNotification), 
                             ct.c_int(self.cNotifyInstallCallback), 
                             callback, 
                             ct.c_int(0))
        print("Result of installing callback: ", ret)

    def remove_callback(self):
        self.dll.Instantiate(ct.c_int(self.cInstNotification), 
                             ct.c_int(self.cNotifyRemoveCallback), 
                             ct.c_int(0), 
                             ct.c_int(0))

    
    
@include_remote_methods(WavemeterWorker)
class Wavemeter(DeviceOverZeroMQ):
    """ Simple stub for the class to be accessed by the user """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        
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
        #self.voltageDisplay.setValue(status["voltage"])
        pass