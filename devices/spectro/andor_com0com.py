# -*- coding: utf-8 -*-
"""
"""

from .spectrometer import *
from PyQt5 import QtWidgets,QtCore
import numpy as np

class AndorCom0ComWorker(SpectrometerWorker):
    
    def __init__(self, *args, port="COM8", baudrate=500000, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = port
        self.baudrate = baudrate
        self.spectrum_started = False
        self.buffer = b''
        self.latest_data = None
        
    def init_device(self):
        import pyvisa
        rm = pyvisa.ResourceManager()
        self.ser = rm.open_resource(self.port)
        self.ser.baud_rate = 500000
        self.ser.read_termination=chr(7)
        self.send_handshake()
   
    def send_handshake(self):
        self.ser.write_raw('helo\r')
        while True:
            ret = self.ser.read_raw(1000)
            if ret== b'ehlo\7':
                print("Handshake successful")
                return True
               
    def set_cooler(self, state):
        pass
    
    def get_cooler_state(self):
        return True
    
    def get_temperature(self):
        return np.nan
        
    def set_exposure(self, exp_time, number):
        pass
    
    def get_exposure_time(self):
        """ Returns a tuple with exposure time (in seconds) and number of 
        accumulations """
        return (0, 1)
    
    def start_single_acquisition(self):
        self.ser.write_raw('getS\r')
        self.spectrum_started = True
        self.buffer = b''
    
    def start_acquisition(self, continuous=False):
        self.start_single_acquisition()
    
    def parse_spectrum(self):
        data = [list(map(float, line.split())) for line in  self.buffer.splitlines()[:-1]]
        data = np.array(data)
        self.latest_data = (data[:,0],data[:,1])
        self.send_via_pubchannel(b'spectrum', self.latest_data)
    
    def check_if_spectrum_ready(self):
        if not self.spectrum_started:
            return
        while self.ser.bytes_in_buffer > 0:
            self.buffer += self.ser.read_raw(self.ser.bytes_in_buffer)
            if self.buffer[-1] == 7:
                return self.parse_spectrum()
                
    
    def acquisition_status(self):
        self.check_if_spectrum_ready()
        if self.spectrum_started:
            return 'running'
        else:
            return 'idle'

    def get_latest_data(self):
        self.check_if_spectrum_ready()
        return self.latest_data