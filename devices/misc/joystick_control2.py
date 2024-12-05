# -*- coding: utf-8 -*-
"""
"""

from PyQt5 import QtCore, QtWidgets, QtGui
import jsonpickle
from ..misc.xbox2 import XBox2Pad
import time

dead_zone = 0.15


class Master():
    def __init__(self, axis_id, combo, checkInverted, editSpeed):
        self.axis_id = axis_id
        self.comboRecentValid = ""
        self.combo = combo
        self.checkInverted = checkInverted
        self.editSpeed = editSpeed

    def dump(self):  # serializes parameters
        self.comboRecentValid = self.combo.currentText()
        return (self.comboRecentValid, self.checkInverted.isChecked(), self.editSpeed.text())

    def restore(self, params):
        self.comboRecentValid = params[0]
        self.checkInverted.setChecked(params[1])
        self.editSpeed.setText(params[2])


class Slave():
    def __init__(self, device, description, axis=None, step=False, method="power"):
        self.device = device
        self.description = description
        self.axis = axis
        self.step = step
        self.method = getattr(device, method)
        self.velocity = 0
        self.last_velocity = 0
        self.last_direction = 0

    def execute(self):
        if self.velocity == self.last_velocity and abs(self.velocity) < 0.000001:
            self.velocity = 0
            return
        self.last_velocity = self.velocity
        if self.step == False:  # continous movement
            if self.axis != None:
                self.method(self.axis, self.velocity)
                self.velocity = 0
            else:
                self.method(self.velocity)
                self.velocity = 0
        else:  # step movement
            if self.velocity < 0:
                self.direction = -1
            elif self.velocity > 0:
                self.direction = 1
            else:
                self.direction = 0

            if self.direction != 0 and self.direction != self.last_direction:
                if self.axis != None:
                    self.device.moveSteps(self.axis, self.direction)
                    self.velocity = 0
                else:
                    self.device.moveSteps(self.direction)
                    self.velocity = 0
            self.last_direction = self.direction
            self.velocity = 0

    def add_change(self, v):
        self.velocity += v


class JoystickControlWidget(QtWidgets.QWidget):
    """ A widget for interactive control of APT motors or attocube axes using XBoxPad """

    def __init__(self, slave_devices=[], parent=None):
        super().__init__(parent)
        self.device_list = slave_devices
        self.xbox = None
        try:
            for xboxname, xbox in {k: v for k, v in self.device_list.items() if isinstance(v, XBox2Pad)}.items():
                self.xbox = xbox
                break
        except Exception as e:
            print(e)
        if self.xbox == None:
            from src.measurement_tab import NoRequiredDevicesError
            raise NoRequiredDevicesError("No XBoxPad 2 found")

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(5000)
        self.timer.timeout.connect(self.timeout)
        self.active = False

        self._createWidgets()
        self.loadSettings()

    axes = [("l_thumb_x", "Left stick horizontal"),
            ("l_thumb_y", "Left stick vertical"),
            ("r_thumb_x", "Right stick horizontal"),
            ("r_thumb_y", "Right stick vertical"),
            ('left_trigger', "Left trigger"),
            ('right_trigger', "Right trigger"),
            ("button1", "D-pad up button"),
            ("button2", "D-pad down button"),
            ("button4", "D-pad right button"),
            ("button3", "D-pad left button"),
            ("button5", "START (arrow right)"),
            ("button6", "BACK (arrow left)"),
            ("button7", "Left stick button"),
            ("button8", "Right stick button"),
            ("button16", "Y button"),
            ("button13", "A button"),
            ("button14", "B button"),
            ("button15", "X button")]

    def refreshCombos(self):
        for master in self.masters:
            n = master.combo.currentIndex()
            master.combo.clear()
            master.combo.addItem("None")
            for slave in self.slaves:
                master.combo.addItem(slave.description)
            master.combo.setCurrentText(master.comboRecentValid)

    def findSlaves(self):
        """ Search through list of devices to find usable slaves to be controlled"""
        self.start(False)
        self.slaves = []
        try:
            from ..can import Can
            for devname, can in {k: v for k, v in self.device_list.items() if isinstance(v, Can)}.items():
                for name, id in can.axes():
                    description = name + "(" + str(id) + ")"
                    self.slaves.append(Slave(can, description, id, step=False, method="power"))
                for name, id in can.servos():
                    description = name + "(" + str(id) + ")"
                    self.slaves.append(Slave(can, description, id, step=False, method="servo"))
                self.slaves.append(Slave(can, "throttle", 0, step=False, method="drive"))
                self.slaves.append(Slave(can, "turning right", 1, step=False, method="drive"))
        except Exception as e:
            print(e)

        try:
            from ..attocube.anc350 import ANC350
            for name, anc350 in {k: v for k, v in self.device_list.items() if isinstance(v, ANC350)}.items():
                for axis in anc350.axes():
                    description = "Attocube %s axis: %d" % (name, axis)
                    self.slaves.append(Slave(anc350, description, axis, step=False, method="moveVelocity"))
                    # description_step = "Attocube %s axis: %d single step" % (name, axis)
                    # self.slaves.append(Slave(anc350, description_step, axis, step=True))
        except Exception as e:
            print(e)

        self.refreshCombos()

    def _createWidgets(self):
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        self.masters = []

        for row, (axis_id, label) in enumerate(self.axes):
            layout.addWidget(QtWidgets.QLabel(label), row, 0)
            combo = QtWidgets.QComboBox()
            combo.addItem("None")
            combo.setMinimumWidth(230)
            layout.addWidget(combo, row, 1)
            layout.addWidget(QtWidgets.QLabel("Inv.:"), row, 2)
            checkInverted = QtWidgets.QCheckBox();
            layout.addWidget(checkInverted, row, 3)
            layout.addWidget(QtWidgets.QLabel("Multiplier:"), row, 4)
            editSpeed = QtWidgets.QLineEdit()
            editSpeed.setValidator(QtGui.QDoubleValidator())
            layout.addWidget(editSpeed, row, 5)
            self.masters.append(Master(axis_id, combo, checkInverted, editSpeed))

        buttonlayout = QtWidgets.QHBoxLayout()
        self.refreshButton = QtWidgets.QPushButton("Refresh")
        self.refreshButton.clicked.connect(self.findSlaves)
        buttonlayout.addWidget(self.refreshButton)
        self.startButton = QtWidgets.QPushButton("Start control")
        self.startButton.setCheckable(True)
        self.startButton.clicked.connect(self.start)
        self.startButton.clicked.connect(self.saveSettings)
        buttonlayout.addWidget(self.startButton)
        layout.addLayout(buttonlayout, len(self.masters) + 2, 0, 1, 6)
        layout.setColumnStretch(5, 6)
        layout.setRowStretch(len(self.masters) + 1, 16)

    def loadSettings(self):
        try:
            with open("config\\joystick_control2.cfg", "r") as file:
                list = jsonpickle.decode(file.read())
                for i in range(len(list)):
                    if i < len(self.masters):
                        self.masters[i].restore(list[i])
        except Exception as e:
            print(e)

    def saveSettings(self):
        try:
            with open("config\\joystick_control2.cfg", "w") as file:
                file.write(jsonpickle.encode([master.dump() for master in self.masters]))
        except Exception as e:
            print(e)

    def start(self, activate=True):
        self.active = activate
        if activate:
            self.startButton.setText("Stop control")
            self.startButton.setChecked(True)
            #for master in self.masters:
            #    master.combo.setDisabled(True)
            self.timer.start()
        else:
            self.startButton.setText("Start control")
            self.startButton.setChecked(False)
            for master in self.masters:
                #master.combo.setEnabled(True)
                slave_nr = master.combo.currentIndex() - 1
                if slave_nr >= 0:
                    self.slaves[slave_nr].execute()  # set zero value

    def timeout(self):
        if not self.active:
            return
        state = self.xbox.currentStatus()
        boost = 1

        if state["connected"]:
            if state["button9"]:
                boost *= 10
            if state["button10"]:
                boost *= 10
        else:
            boost = 1

        for master in self.masters:
            if master.axis_id not in state:
                continue

            if state["connected"]:
                value = state[master.axis_id]
            else:
                value = 0

            if master.axis_id in ["l_thumb_x", "l_thumb_y", "r_thumb_x", "r_thumb_y"]:
                if abs(value) < dead_zone:
                    value = 0
                else:
                    value = value * (abs(value) - dead_zone) / (1 - dead_zone)

            if master.checkInverted.isChecked():
                value = -value

            if len(master.editSpeed.text()) != 0:
                try:
                    value *= float(master.editSpeed.text()) * boost
                except Exception as e:
                    print(e)

            slave_nr = master.combo.currentIndex() - 1
            if slave_nr >= 0:
                self.slaves[slave_nr].add_change(value)

        for slave in self.slaves:
            slave.execute()

        self.timer.start(80)