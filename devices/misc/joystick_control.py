# -*- coding: utf-8 -*-
"""
"""

from PyQt5 import QtCore,QtWidgets,QtGui
import time

dead_zone = 0.12

def _create_apt_slave(apt, serial):
    """Creates a pair of a name and a function to move a stage """
    func = lambda velocity : apt.moveVelocity(serial, velocity)
    return ("APT s/n: %d" % serial, func)

class Master():
    def __init__(self, axis_id, combo, checkInverted, editSpeed):
        self.axis_id = axis_id
        self.combo = combo
        self.checkInverted = checkInverted
        self.editSpeed = editSpeed

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
        for master in self.masters:
            n = master.combo.currentIndex()
            master.combo.clear()
            master.combo.addItem("None")
            for s in self.slaves:
                master.combo.addItem(s[0])
            master.combo.setCurrentIndex(n)

    

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
            layout.addWidget(QtWidgets.QLabel("Inv.:"), row, 2)
            checkInverted = QtWidgets.QCheckBox();
            layout.addWidget(checkInverted, row, 3)
            layout.addWidget(QtWidgets.QLabel("Multiplier:"), row, 4)
            editSpeed = QtWidgets.QLineEdit()
            editSpeed.setValidator(QtGui.QDoubleValidator())
            layout.addWidget(editSpeed, row, 5)
            self.masters.append( Master(axis_id, combo, checkInverted, editSpeed) )

        buttonlayout = QtWidgets.QHBoxLayout()
        self.refreshButton = QtWidgets.QPushButton("Refresh")
        self.refreshButton.clicked.connect(self.findSlaves)
        buttonlayout.addWidget(self.refreshButton)            
        self.startButton = QtWidgets.QPushButton("Start control")
        self.startButton.setCheckable(True)
        self.startButton.clicked.connect(self.start)
        buttonlayout.addWidget(self.startButton)
        layout.addLayout(buttonlayout, len(self.masters)+2,0,1,6)
        layout.setColumnStretch(5,6)
        layout.setRowStretch(10,6)
        
    def start(self, activate=True):
        self.active = activate
        if activate:
            self.startButton.setText("Stop control")
            self.startButton.setChecked(True)
            for master in self.masters:
                master.combo.setDisabled(True)
            self.timer.start()
        else:
            self.startButton.setText("Start control")
            self.startButton.setChecked(False)
            for master in self.masters:
                master.combo.setEnabled(True)
                slave_nr = master.combo.currentIndex() - 1
                if slave_nr >= 0:
                    self.slaves[slave_nr][1](0)
            
    def timeout(self):
        if not self.active:
            return
        state = self.xbox.currentStatus()

        for master in self.masters:
            if master.axis_id not in state:
                continue
            value = state[master.axis_id] * 2
            if abs(value) < dead_zone:
                value = 0
            else:
                value = value * (abs(value) - dead_zone) / (1 - dead_zone)
            if master.checkInverted.isChecked():
                value = -value
            if len(master.editSpeed.text()) != 0:
                value *= float(master.editSpeed.text())
            slave_nr = master.combo.currentIndex() - 1
            if slave_nr >= 0:
                self.slaves[slave_nr][1](value)
        self.timer.start(80)