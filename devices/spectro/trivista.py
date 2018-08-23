# -*- coding: utf-8 -*-
"""
Created on Tue May 15 11:50:03 2018

@author: dms
"""

import sys
import clr
import time
from devices import Device
import numpy as np

assemblyPath = "C:\\Program Files\\S&I VistaControl"
if assemblyPath not in sys.path:
    sys.path.append(assemblyPath)

clr.AddReference("VistaControl")


from VistaControl.Remoting import Client,ICallback,Frame


class myCallback(ICallback):
    __namespace__ = "blabla"
    
    def __init__(self):
        pass
    
    def DataChanged(self,frame):
        pass


class Trivista(Device):
    def __init__(self, hostname="localhost", **kwargs):
        super().__init__(**kwargs)
        self.client = Client()
        self.framebuf = myCallback() #FrameBuffer()       
        if self.client.Connect(self.framebuf,hostname,8000,'VistaControl'):
            print("Trivista connected successfully")
        else:
            print("Error connecting to Trivista")
        self.pipe = self.client.pipeProxy
    
    def __del__(self):
        pass
    
    def start_accumulation(self):
        self.pipe.StopAcquisition()
        self.pipe.StartSingleAcquisition()
    
    def is_accumulation_finished(self):
        return self.pipe.GetAcquisitionState() not in [1,2] #InProgress=1, NewFrameAvailable=2
    
    def cancel_accumulation(self):
        pass
    
    def get_spectrum(self):      
        frame = self.pipe.GetActualData()
        return np.array(list(frame.xAxis.calibrationData)), np.array(list(frame.data))
        
    def createDock(self, parent, menu):
        pass
        
