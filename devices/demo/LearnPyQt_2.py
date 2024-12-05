# -*- coding: utf-8 -*-
"""
Created on Tue Sep 18 10:50:32 2018

@author: dms
"""

import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, 
    QHBoxLayout, QVBoxLayout, QApplication)
from PyQt5 import QtWidgets, QtCore, QtGui

class Example(QWidget):
    
    def __init__(self):
        super().__init__()
        
        self.initUI()
        
    def closeEvent(self,event):
        print("close 'x' was pressed")
    def initUI(self):
        d = {}
        d["my_int"] = 137
        d["my_float"] = 3.24542455
        d["my_bool"] = True
        d["my_str"] = "Kaszanka z boczkiem"
        d["my_list"] = [1,1.2,1.4,77.9]
        d["my_none"] = None
        
        def MakeGuiFromDic(d):
            layout = QtWidgets.QGridLayout()
            self.setLayout(layout)
            gui_elements={}
            for (row,label) in enumerate(d):
                
                if isinstance(d[label],bool):
                    print("bool bool bool")
                    l=QtWidgets.QLabel(label)                    
                    layout.addWidget(l,row,1)
                    b=QtWidgets.QRadioButton()
                    gui_elements[label]=[b]
                    layout.addWidget(b,row,2)
                elif isinstance(d[label],float):
                    print("float")
                    l=QtWidgets.QLabel(label)                    
                    layout.addWidget(l,row,1)
                    x=QtWidgets.QLCDNumber()
                    x.setSegmentStyle(QtWidgets.QLCDNumber.Flat)
                    gui_elements[label]=[l,x]
                    layout.addWidget(x,row,2)
                elif isinstance(d[label],int):
                    print("int")
                    l=QtWidgets.QLabel(label)                    
                    layout.addWidget(l,row,1)
                    x=QtWidgets.QLCDNumber()
                    x.setSegmentStyle(QtWidgets.QLCDNumber.Flat)
                    gui_elements[label]=[l,x]
                    layout.addWidget(x,row,2)
                elif isinstance(d[label],str):
                    l=QtWidgets.QLabel(label)
                    layout.addWidget(l,row,1)
                    x=QtWidgets.QLabel(d[label])                    
                    gui_elements[label]=[l,x]
                    layout.addWidget(x,row,2)
                elif isinstance(d[label],list):
                    layout.addWidget(QtWidgets.QLabel(label),row,1)
                    layout.addWidget(QtWidgets.QLabel(str(d[label])),row,2)
                elif d[label] is None:
                    layout.addWidget(QtWidgets.QLabel(label),row,1)
                    layout.addWidget(QtWidgets.QLabel(str(d[label])),row,2)
                else:
                    print("else else else")
                    layout.addWidget(QtWidgets.QLabel(label),row,1)
                    layout.addWidget(QtWidgets.QLabel("UFO"),row,2)
            return gui_elements,layout
        
        g,ly=MakeGuiFromDic(d)
        print(g)
        self.show()
        
        
if __name__ == '__main__':
    try:
        app
    except:
        print("kasakaka")
        app = QApplication(sys.argv)
    ex = Example()
    app.exec_()