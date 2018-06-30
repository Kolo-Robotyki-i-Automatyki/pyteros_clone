# -*- coding: utf-8 -*-
"""
Created on Tue May 15 11:50:03 2018

@author: dms
"""

import sys
import clr
import time

assemblyPath = "C:\\Program Files\\S&I VistaControl"
if assemblyPath not in sys.path:
    sys.path.append(assemblyPath)

clr.AddReference("VistaControl")
#clr.AddReference("VistaRemote.Extras")



from VistaControl.Remoting import Client,ICallback,Frame
#from VistaRemoteExtras import FrameBuffer

class myCallback(ICallback):
    __namespace__ = "blabla"
    
    def __init__(self):
        pass
    
    def DataChanged(self,frame):
        pass


class Trivista:
    def __init__(self, host="localhost"):
        self.client = Client()
        self.framebuf = myCallback() #FrameBuffer()       
        if self.client.Connect(self.framebuf,host,8000,'VistaControl'):
            print("Trivista connected successfully")
        else:
            print("Error connecting to Trivista")
    
    def __del__(self):
        pass
    
    def getSpectrum(self):
        pp = self.client.pipeProxy
        pp.StopAcquisition()
        pp.StartSingleAcquisition()
        while(pp.GetAcquisitionState() in [1,2]): #InProgress=1, NewFrameAvailable=2
            time.sleep(0.1)
        frame = pp.GetActualData()
        return list(frame.xAxis.calibrationData), list(frame.data)
        