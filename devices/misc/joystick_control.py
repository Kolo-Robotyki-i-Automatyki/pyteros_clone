# -*- coding: utf-8 -*-
"""
"""

from PyQt5 import QtCore,QtWidgets
import time



def _create_apt_slave(apt, serial):
    """Creates a pair of a name and a function to move a stage """
    func = lambda velocity : apt.moveVelocity(serial, velocity)
    return ("APT s/n: %d" % serial, func)

class JoystickControlWidget(QtWidgets.QWidget):
    """ A widget for interactive control of APT motors using XBoxPad """
    
    def __init__(self, xbox, slave_devices=[], parent=None):
        super().__init__(parent)
        self.xbox = xbox
        self.device_list = slave_devices
        self.slaves = []
        
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(5000)
        self.timer.timeout.connect(self.timeout)
        self.active = False
        
        self._createWidgets()        
        
    axes =  [("l_thumb_x", "Left stick horizontal"),
             ("l_thumb_y", "Left stick vertical"),
             ("r_thumb_x", "Right stick horizontal"),
             ("r_thumb_y", "Right stick vertical"),
             ('left_trigger', "Left trigger"),
             ('right_trigger', "Right trigger")]
    

    def refreshCombos(self):
        for axis_id,combo in self.masters:
            n = combo.currentIndex()
            combo.clear()
            combo.addItem("None")
            for s in self.slaves:
                combo.addItem(s[0])
            combo.setCurrentIndex(n)

    

    def findSlaves(self):
        """ Search through list of devices to find usable slaves to be controlled"""
        self.start(False)
        self.slaves = []
        
        try:
            from ..thorlabs.apt import APT
            for apt in filter(lambda d: isinstance(d, APT), self.device_list):
                for serial in apt.devices():
                    self.slaves.append( _create_apt_slave(apt,serial) )
        except Exception as e:
            print(e)
            
        self.refreshCombos()
                
        
    def _createWidgets(self):
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        self.masters = []
    
        for row, (axis_id, label) in enumerate(self.axes):
            layout.addWidget(QtWidgets.QLabel(label),row,0)
            combo = QtWidgets.QComboBox()
            combo.addItem("None")
            combo.setMinimumWidth(200)
            layout.addWidget(combo, row, 1)
            self.masters.append( (axis_id, combo) )

        buttonlayout = QtWidgets.QHBoxLayout()
        self.refreshButton = QtWidgets.QPushButton("Refresh")
        self.refreshButton.clicked.connect(self.findSlaves)
        buttonlayout.addWidget(self.refreshButton)            
        self.startButton = QtWidgets.QPushButton("Start control")
        self.startButton.setCheckable(True)
        self.startButton.clicked.connect(self.start)
        buttonlayout.addWidget(self.startButton)
        layout.addLayout(buttonlayout, len(self.masters)+2,0,1,3)
        layout.setColumnStretch(5,6)
        layout.setRowStretch(10,6)
        
    def start(self, activate=True):
        self.active = activate
        if activate:
            self.startButton.setText("Stop control")
            self.startButton.setChecked(True)
            for axis_id,combo in self.masters:
                combo.setDisabled(True)
            self.timer.start()
        else:
            self.startButton.setText("Start control")
            self.startButton.setChecked(False)
            for axis_id,combo in self.masters:
                combo.setEnabled(True)
                slave_nr = combo.currentIndex() - 1
                if slave_nr >= 0:
                    self.slaves[slave_nr][1](0)
            
    def timeout(self):
        if not self.active:
            return
        state = self.xbox.currentStatus()

        for axis_id,combo in self.masters:
            if axis_id not in state:
                continue
            value = state[axis_id]*2
            if abs(value) < 0.1:
                value = 0
            slave_nr = combo.currentIndex() - 1
            if slave_nr >= 0:
                self.slaves[slave_nr][1](value)
        self.timer.start(80)