# -*- coding: utf-8 -*-
"""
"""

from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler
from .spectrometer import *
from PyQt5 import QtWidgets,QtCore

class SpectrometerWithCCDWorker(SpectrometerWorker):
    
    def __init__(self, ccd="andor", ccd_id=None, mono="acton", mono_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.dev_params = {"ccd":ccd, "ccd_id":ccd_id, "mono":mono, "mono_id":mono_id}
        
    def init_device(self):
        if self.dev_params["ccd"] == "andor":
            from . import pyandor
            self.ccd = pyandor.Andor(self.dev_params["ccd_id"])
            self.ccd.SetTemperature(-65)
        else:
            raise Exception("Unsupported CCD type: %s" % self.dev_params["ccd"])
        
        if self.dev_params["mono"] == "acton":
            pass
        elif self.dev_params["mono"] == "shamrock":
            pass
        else:
            raise Exception("Unsupported monochromator type: %s" % self.dev_params["mono"])
   
    def set_cooler(self, state):
        """ state is True or False """
        if state:
            self.ccd.CoolerON()
        else:
            self.ccd.CoolerOFF()
    
    def get_cooler_state(self):
        return bool(self.ccd.IsCoolerOn())
    
    def get_temperature(self):
        return self.ccd.GetTemperature()

    def get_target_temperature(self):
        return self.ccd.set_T
        
    def set_exposure(self, exp_time, number):
        self.ccd.SetSingleScan()
        self.ccd.SetTriggerMode(7)
        self.ccd.SetExposureTime(exp_time)
    
    def get_exposure_time(self):
        """ Returns a tuple with exposure time (in seconds) and number of 
        accumulations """
        exposure,accumulate = self.ccd.GetAcquisitionTimingsNorm()
        return (exposure, 1)
    
    def start_acquisition(self, continuous=False):
        self.ccd.StartAcquisition()
    
    def acquisition_status(self):
        return self.ccd.GetStatusNorm()

    def get_latest_data(self):
        ydata = self.ccd.GetAcquiredDataAsArray()
        xdata = np.arange(len(ydata))
        self.send_via_pubchannel(b'spectrum', (xdata,ydata))
        return xdata,ydata