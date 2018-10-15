# -*- coding: utf-8 -*-
"""
Created on Tue Aug 21 10:54:18 2018

@author: Turing
"""




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
        self.dll.EnsembleMotionWaitMode(self.handle, ct.c_int(0));
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
        widget = QtWidgets.QWidget(dock)
        self.layout = QtWidgets.QVBoxLayout(parentWidget)
        
        btn=QtWidgets.QPushButton("Position: "+str(round(self.position(),3)),widget)
        
        grid = QtWidgets.QGridLayout()
        widget.setLayout(grid)
        grid.addWidget(btn,0,0)
        
        
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        
        
        grid2=QtWidgets.QGridLayout()
        delayline=QtWidgets.QWidget(dock)
        delayline.setLayout(grid2)
        btn1=QtWidgets.QPushButton(">>",delayline)
        btn2=QtWidgets.QPushButton("<<",delayline)
        btn3=QtWidgets.QLineEdit("5",delayline)
        btn4=QtWidgets.QPushButton("Minimalize",delayline)
        btn5=QtWidgets.QPushButton("Refresh",delayline)
        positionBox=QtWidgets.QLineEdit(delayline)
        positionBox.setText("Position: "+str(round(self.position(),3)))
        grid2.addWidget(positionBox,1,1,1,3)
        grid2.addWidget(btn1,2,1)
        grid2.addWidget(btn2,2,2)
        grid2.addWidget(btn3,2,3)
        grid2.addWidget(btn4,2,4)
        grid2.addWidget(btn5,1,4)
        
        
        delayline.hide()
        
        def hideDialog():
            dock.setWidget(widget)
            
        def skipp():
            try:
                self.move(self.position() + float(btn3.text()),0)
                
            except:
                print("Wrong value")
                
        def refresh():
            positionBox.setText("Position: " +str(round(self.position(),3)))
            btn.setText("Position: " +str(round(self.position(),3)))
        def skipm():
            try:
                self.move(self.position() - float(btn3.text()),0)
                
            except:
                print("Wrong value")
        
        def showDialog():
            dock.setWidget(delayline)
        
        btn.clicked.connect(showDialog)
        btn1.clicked.connect(skipp)
        btn2.clicked.connect(skipm)
        btn4.clicked.connect(hideDialog)
        btn5.clicked.connect(refresh)
        
        def goToDialog(this):
            pos,ok = QtWidgets.QInputDialog.getDouble(None, "Go to position", "New position:",0,-500,500,3)
            if ok:
                    QtWidgets.QApplication.processEvents()
                    self.move(pos,False)
                    
                    
            
                
        positionBox.mousePressEvent = goToDialog
        if menu:
            menu.addAction(dock.toggleViewAction())
        
        self.timer = QtCore.QTimer()
        
        self.timer.timeout.connect(refresh)
        self.timer.start(100)
            
        
        
        # create a line edit and a button

        
    
             

        
        
   
        
    
   
    
    
   

    

