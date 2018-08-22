# -*- coding: utf-8 -*-
"""
Created on Tue Aug 21 10:54:18 2018

@author: Turing
"""

from PyQt5 import QtWidgets,QtCore


import ctypes as ct


from PyQt5 import QtWidgets, QtCore, QtGui
import time


import os
os.environ["PATH"] = os.path.dirname(__file__)+ os.pathsep + os.environ["PATH"]

class DelayLine:    
    def __init__(self):
        try:
            self.dll = ct.windll.LoadLibrary("EnsembleC64.dll")
        except OSError:
            self.dll = ct.windll.LoadLibrary("EnsembleC.dll")
        except:
            print("Loading library failed")
        handles = (ct.POINTER(ct.c_void_p))()
        handle_count = ct.c_int()
        
        if self.dll.EnsembleConnect(ct.byref(handles), ct.byref(handle_count) ):
            print("Delay Line connected")
            self.handle=handles[0]
            self.handle_count = handle_count.value
            print("handle:",self.handle," ","number of axis:",self.handle_count)
        self.dll.EnsembleMotionEnable(self.handle,ct.c_int(self.handle_count))
        
    def home(self):
        self.dll.EnsembleMotionHome(self.handle,ct.c_int(self.handle_count))
        
        
    def move(self,distance,wait=True):
        self.cdistance=ct.c_double *2
        self.cspeed=ct.c_double *2
        self.dll.EnsembleMotionMoveAbs(self.handle, ct.c_int(self.handle_count), self.cdistance(distance,0), self.cspeed(10,0))
        if wait:
            self.dll.EnsembleMotionWaitForMotionDone(self.handle, ct.c_int(self.handle_count) ,ct.c_int(0), ct.c_int(-1), None)
           
    def position(self):
        position=ct.c_double()
        self.dll.EnsembleStatusGetItem(self.handle, ct.c_int(0), ct.c_int(1), ct.byref(position))
        return position.value
    
    def createDock(self, parentWidget, menu = None):
        """ Function for integration in GUI app.  """
        dock = QtWidgets.QDockWidget("Delay Line Aerotech", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        self.layout = QtWidgets.QVBoxLayout(parentWidget)
        widget.setLayout(self.layout)
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())

        self.createListenerThread(self.updateSlot)
    

    
   
    
    
   

    

