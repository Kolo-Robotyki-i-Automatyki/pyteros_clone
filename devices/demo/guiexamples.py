# -*- coding: utf-8 -*-
"""
Created on Tue Aug 21 10:54:18 2018

@author: Turing
"""
      
from datetime import datetime
import time
from time import sleep
from time import perf_counter as clock
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets, QtCore, QtGui


default_req_port = 1212
default_pub_port = 1313

class DummyGUIWorker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
   
        self._dummy_var1 = 0
        self._dummy_var2 = False
        self._dummy_var3 = None

    def status(self):
        d = super().status()
        d["dummy1"] = 1
        d["dummy2"] = 1
        d["dummy3"] = 1
        d["time"] = self.now_datetime()
        print("status called")
        return d

    def init_device(self):
        """
        Opens the communication and starts the polling thread for IPS
        """
        print("init_device in worker Success")
        
    def close_device(self):
        self.continue_running = False

   
    @remote
    def now_datetime(self):
        t=str(datetime.now())
        print("DummyGUIWorker "+t)
        return t

    @remote
    def dummy_functionA(self):
        print(" dummy function A")
        
    @remote
    def dummy_functionB(self):
        print(" dummy function B")

   

@include_remote_methods(DummyGUIWorker)
class DummyGUI(DeviceOverZeroMQ):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

    def __del__(self):
        pass

    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("DummyGUI Window Name", parentWidget)
        widget1 = QtWidgets.QWidget(dock)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        
        
        self.LCD=QtWidgets.QLCDNumber()
        self.LCD.setSegmentStyle(QtWidgets.QLCDNumber.Flat)
        self.btn_settings = QtWidgets.QPushButton("Settings")
        self.btn_settings.setToolTip('This is an example button')
        self.btn_settings.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
        QtWidgets.QSizePolicy.Fixed)

        layout.addWidget(self.btn_settings)
        layout.addWidget(self.LCD)

        
        widget1.setLayout(layout)
        dock.setWidget(widget1)

        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        
        #second window with advanced settings
        grid = QtWidgets.QGridLayout(parentWidget)
        widget2=QtWidgets.QWidget(dock)

        
        self.comboBox=QtWidgets.QComboBox()
        self.comboBox.addItem("Kosiarka")
        self.comboBox.addItem("Korniszon")
        self.comboBox.addItem("Kanapka z chlebem")
        self.comboBox.setToolTip('This is an example comboBox')
        self.comboBox.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
        QtWidgets.QSizePolicy.Fixed)
        
        self.LCD2=QtWidgets.QLCDNumber()
        self.LCD2.setSegmentStyle(QtWidgets.QLCDNumber.Flat)
        
        self.btn_min = QtWidgets.QPushButton("min")
        self.btn_min.setToolTip('This is an example button')
        self.btn_min.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
        QtWidgets.QSizePolicy.Fixed)
        
        grid.addWidget(self.comboBox,1,1)
        grid.addWidget(self.LCD2,1,2)
        grid.addWidget(self.btn_min,4,1)
        widget2.setLayout(grid)
        widget2.hide()
        
        def hideDialog():
            dock.setWidget(widget1)
            
        def showDialog():
            dock.setWidget(widget2)
            
        self.btn_settings.clicked.connect(showDialog)
        self.btn_min.clicked.connect(hideDialog)
        
        
        if menu:
            menu.addAction(dock.toggleViewAction())

        #self.createListenerThread(self.updateSlot)



    def updateSlot(self, status):
        self.LCD.display(status["time"][17:19])




             

        
        
   
        
    
   
    
    
   

    

