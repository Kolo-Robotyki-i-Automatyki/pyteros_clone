# -*- coding: utf-8 -*-
"""
"""

from PyQt5 import QtCore,QtWidgets,QtGui
import jsonpickle
from ..misc.xbox import XBoxPad
import time

dead_zone = 0.15

def _create_apt_slave(apt, name, serial):
    """Creates a pair of a name and a function to move a stage """
    func = lambda velocity : apt.moveVelocity(serial, velocity)
    return ("APT %s, s/n: %d" % (name, serial), func)

def _create_anc350_slave(anc350, name, axis):
    """Creates a pair of a name and a function to move a stage """
    def f(velocity):
        anc350.moveVelocity(axis, int(velocity))
    #func = lambda velocity : anc350.moveVelocity(axis, velocity)
    return ("Attocube %s axis: %d" % (name, axis), f)

class Master():
    def __init__(self, axis_id, combo, checkInverted, editSpeed):
        self.axis_id = axis_id
        self.comboRecentValid = ""
        self.combo = combo
        self.checkInverted = checkInverted
        self.editSpeed = editSpeed

    def dump(self): #serializes parameters
        self.comboRecentValid = self.combo.currentText()
        return (self.comboRecentValid, self.checkInverted.isChecked(), self.editSpeed.text())

    def restore(self, params):
        self.comboRecentValid = params[0]
        self.checkInverted.setChecked(params[1])
        self.editSpeed.setText(params[2])

class JoystickControlWidget(QtWidgets.QWidget):
    """ A widget for interactive control of APT motors or attocube axes using XBoxPad """
    
    def __init__(self, slave_devices=[], parent=None):
        super().__init__(parent)
        self.device_list = slave_devices
        self.xbox = None
        try:
            for xboxname, xbox in {k: v for k, v in self.device_list.items() if isinstance(v, XBoxPad)}.items():
                self.xbox = xbox
                break
        except Exception as e:
            print(e)
        if self.xbox == None:
            from src.measurement_tab import NoRequiredDevicesError
            raise NoRequiredDevicesError("No XBoxPad found")

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(5000)
        self.timer.timeout.connect(self.timeout)
        self.active = False
        
        self._createWidgets()
        self.loadSettings()
        
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
            #master.combo.setCurrentIndex(n)
            master.combo.setCurrentText(master.comboRecentValid)

    

    def findSlaves(self):
        """ Search through list of devices to find usable slaves to be controlled"""
        self.start(False)
        self.slaves = []

        try:
            from ..thorlabs.apt import APT
            for name, apt in {k: v for k, v in self.device_list.items() if isinstance(v, APT)}.items():
                for serial in apt.devices():
                    self.slaves.append(_create_apt_slave(apt, name, serial))
        except Exception as e:
            print(e)

        try:
            from ..attocube.anc350 import ANC350
            for name, anc350 in {k: v for k, v in self.device_list.items() if isinstance(v, ANC350)}.items():
                for axis in anc350.axes():
                    self.slaves.append(_create_anc350_slave(anc350, name, axis))
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
        self.startButton.clicked.connect(self.saveSettings)
        buttonlayout.addWidget(self.startButton)
        layout.addLayout(buttonlayout, len(self.masters)+2,0,1,6)
        layout.setColumnStretch(5,6)
        layout.setRowStretch(10,6)

    def loadSettings(self):
        try:
            with open("config\\joystick_control.cfg", "r") as file:
                list = jsonpickle.decode(file.read())
                for i in range(len(list)):
                    if i < len(self.masters):
                        self.masters[i].restore(list[i])
        except Exception as e:
            print(e)

    def saveSettings(self):
        try:
            with open("config\\joystick_control.cfg", "w") as file:
                file.write(jsonpickle.encode([master.dump() for master in self.masters]))
        except Exception as e:
            print(e)

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
        boost = 1

        if state["button9"]:
            boost *= 10
        if state["button10"]:
            boost *= 10

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
                value *= float(master.editSpeed.text()) * boost
            slave_nr = master.combo.currentIndex() - 1
            if slave_nr >= 0:
                self.slaves[slave_nr][1](value)
        self.timer.start(80)