from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from devices.misc.xbox import XBoxPad
from devices.rover import Rover, MoveCommand
from DeviceServerHeadless import get_devices, get_proxy

from collections import deque
import itertools
import jsonpickle
import os
import random
import socket
import struct
import time


class NoRequiredDevicesError(Exception):
	"""Error raised if no devices required for given feature is found."""
	pass


epsilon = 0.00000001
dead_zone = 0.17


class Master():
	def __init__(self, axis_id, combo, checkInverted, editSpeedMax, editSpeedMin, editSpeedSmooth):
		self.axis_id = axis_id
		self.comboRecentValid = ""
		self.combo = combo
		self.checkInverted = checkInverted
		self.editSpeedMax = editSpeedMax
		self.editSpeedMin = editSpeedMin
		self.editSpeedSmooth = editSpeedSmooth
		self.lastvals = deque([0 for i in range(101)])

	def dump(self):  # serializes parameters
		self.comboRecentValid = self.combo.currentText()
		return (
		self.comboRecentValid, self.checkInverted.isChecked(), self.editSpeedMax.text(), self.editSpeedMin.text(),
		self.editSpeedSmooth.text())

	def restore(self, params):
		self.comboRecentValid = params[0]
		self.checkInverted.setChecked(params[1])
		self.editSpeedMax.setText(params[2])
		self.editSpeedMin.setText(params[3])
		self.editSpeedSmooth.setText(params[4])


class Slave():
	def __init__(self, device, description, axis=None, method=MoveCommand.POWER):
		self.device = device
		self.description = description
		self.axis = axis
		self.method = method
		self.velocity = 0
		self.last_velocity = 0
		self.last_direction = 0

	def execute(self):
		try:
			if self.velocity == self.last_velocity and abs(
					self.velocity) < 0.000001:  # and not(self.axis == 190 or self.axis == 191 or self.axis == 201 or self.axis == 200):
				self.velocity = 0
				return (MoveCommand.NOP, None, 0)
			self.last_velocity = self.velocity
			self.velocity = 0
			return (self.method, self.axis, self.last_velocity)
		except Exception as e:
			print("[control] error sending: {}".format(e))
			return (MoveCommand.NOP, None, 0)

	def add_change(self, v):
		self.velocity += v


class JoystickControlWidget(QtWidgets.QWidget):
	""" A widget for interactive control of APT motors or attocube axes using XBoxPad """

	def __init__(self, parent=None):
		super().__init__(parent)
		self.device_list = { dev.name: get_proxy(dev) for dev in get_devices() }
		
		self.xbox = None
		try:
			for xboxname, xbox in {k: v for k, v in self.device_list.items() if isinstance(v, XBoxPad)}.items():
				self.xbox = xbox
				break
		except Exception as e:
			print('[control] browsing devices: {}'.format(e))

		self.cmd_socket = None
		self.cmd_server_addr = None
		self._open_command_socket()

		self.next_packet_id = random.randint(0, 2**31)

		self.timer = QtCore.QTimer()
		self.timer.setSingleShot(5000)
		self.timer.timeout.connect(self.timeout)
		self.active = False

		self.axes = [("l_thumb_x", "Left stick horizontal"),
					 ("l_thumb_y", "Left stick vertical"),
					 ("r_thumb_x", "Right stick horizontal"),
					 ("r_thumb_y", "Right stick vertical"),
					 # ('left_trigger', "Left trigger"),
					 # ('right_trigger', "Right trigger"),
					 ("button4", "D-pad horizontal"),
					 ("button1", "D-pad vertical"),
					 ("button5", "START (arrow right)"),
					 ("button6", "BACK (arrow left)"),
					 # ("button7", "Left stick button"),
					 # ("button8", "Right stick button"),
					 # ("button9", "Left trigger button"),
					 ("button10", "Right trigger button"),
					 ("button16", "Y button"),
					 ("button13", "A button"),
					 ("button14", "B button"),
					 ("button15", "X button"),
					 ("alt_l_thumb_x", "Alt Left stick horizontal"),
					 ("alt_l_thumb_y", "Alt Left stick vertical"),
					 ("alt_r_thumb_x", "Alt Right stick horizontal"),
					 ("alt_r_thumb_y", "Alt Right stick vertical"),
					 # ('alt_left_trigger', "Alt Left trigger"),
					 # ('alt_right_trigger', "Alt Right trigger"),
					 ("alt_button4", "Alt D-pad horizontal"),
					 ("alt_button1", "Alt D-pad vertical"),
					 ("alt_button5", "Alt START (arrow right)"),
					 ("alt_button6", "Alt BACK (arrow left)"),
					 # ("alt_button7", "Alt Left stick button"),
					 # ("alt_button8", "Alt Right stick button"),
					 # ("alt_button9", "Left trigger button"),
					 ("alt_button10", "Alt Right trigger button"),
					 ("alt_button16", "Alt Y button"),
					 ("alt_button13", "Alt A button"),
					 ("alt_button14", "Alt B button"),
					 ("alt_button15", "Alt X button")]

		self._createWidgets()
		self.loadSettings()

	def _open_command_socket(self):
		rover = None
		for _, dev in self.device_list.items():
			if isinstance(dev, Rover):
				rover = dev
				break
		if rover is None:
			return

		host = rover.host
		port = rover.get_cmd_stream_port()

		self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.cmd_server_addr = (host, port)

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
			for devname, can in {k: v for k, v in self.device_list.items() if isinstance(v, Rover)}.items():
				for name, id in can.axes():
					description = name + "(" + str(id) + ")"
					self.slaves.append(Slave(can, description, id, method=MoveCommand.POWER))
				for name, id in can.servos():
					description = name + "(" + str(id) + ")"
					self.slaves.append(Slave(can, description, id, method=MoveCommand.SERVO))
				self.slaves.append(Slave(can, "throttle", 0, method=MoveCommand.DRIVE))
				self.slaves.append(Slave(can, "turning right", 1, method=MoveCommand.DRIVE))
		except Exception as e:
			print('[control] looking for slaves: {}'.format(e))

		self.refreshCombos()

	def _createWidgets(self):
		layout = QtWidgets.QGridLayout()
		layout.setSpacing(2)
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
			layout.addWidget(QtWidgets.QLabel("Max:"), row, 4)
			editSpeedMax = QtWidgets.QLineEdit()
			editSpeedMax.setFixedWidth(60)
			editSpeedMax.setValidator(QtGui.QDoubleValidator())
			layout.addWidget(editSpeedMax, row, 5)
			layout.addWidget(QtWidgets.QLabel("Min:"), row, 6)
			editSpeedMin = QtWidgets.QLineEdit()
			editSpeedMin.setFixedWidth(60)
			editSpeedMin.setValidator(QtGui.QDoubleValidator())
			layout.addWidget(editSpeedMin, row, 7)
			layout.addWidget(QtWidgets.QLabel("Smooth:"), row, 8)
			editSpeedSmooth = QtWidgets.QLineEdit()
			editSpeedSmooth.setFixedWidth(60)
			editSpeedSmooth.setValidator(QtGui.QDoubleValidator())
			layout.addWidget(editSpeedSmooth, row, 9)
			layout.setColumnStretch(10, 10)
			self.masters.append(Master(axis_id, combo, checkInverted, editSpeedMax, editSpeedMin, editSpeedSmooth))

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
		#try:
		with open("config" + os.sep + "joystick_control.cfg", "r") as file:
			list = jsonpickle.decode(file.read())
			for i in range(len(list)):
				if i < len(self.masters):
					self.masters[i].restore(list[i])
		#except Exception as e:
		#    # print(e)
		#    pass

	def saveSettings(self):
		try:
			with open("config" + os.sep + "joystick_control.cfg", "w") as file:
				file.write(jsonpickle.encode([master.dump() for master in self.masters]))
		except Exception as e:
			print(e)

	def start(self, activate=True):
		self.active = activate
		if activate:
			self.startButton.setText("Stop control")
			self.startButton.setChecked(True)
			self.timer.start()
		else:
			self.startButton.setText("Start control")
			self.startButton.setChecked(False)
			for master in self.masters:
				slave_nr = master.combo.currentIndex() - 1
				if slave_nr >= 0:
					self.slaves[slave_nr].execute()  # set zero value

	def timeout(self):
		if not self.active:
			return
		try:
			state_raw = self.xbox.currentStatus()
		except:
			state_raw = {"connected": False}
		boost = 1
		if state_raw["connected"]:
			boost *= (1 - state_raw["left_trigger"])
			boost *= (1 + state_raw["right_trigger"])
		else:
			self.timer.start(40)
			return state_raw


		state = {}
		alt = (state_raw['button9'] > 0)
		for axis in state_raw:
			if axis == 'connected':
				state['connected'] = state_raw['connected']
				continue
			if alt:
				state['alt_' + axis] = state_raw[axis]
				state[axis] = 0
			else:
				state['alt_' + axis] = 0
				state[axis] = state_raw[axis]

		for master in self.masters:
			# print(master.axis_id)
			if master.axis_id not in state:
				continue
			if state["connected"]:
				value = state[master.axis_id]
			else:
				value = 0
			# print(value)
			if master.axis_id in ["l_thumb_x", "l_thumb_y", "r_thumb_x", "r_thumb_y",
								  "alt_l_thumb_x", "alt_l_thumb_y", "alt_r_thumb_x", "alt_r_thumb_y"]:
				if abs(value) < dead_zone:
					value = 0
				else:
					value = value * (abs(value) - dead_zone) / (1 - dead_zone)

			if master.checkInverted.isChecked():
				value = -value

			minv = 0
			maxv = 1
			smooth = 0
			try:
				maxv = float(master.editSpeedMax.text())
			except Exception as e:
				pass
			try:
				minv = float(master.editSpeedMin.text())
			except Exception as e:
				pass
			try:
				smooth = float(master.editSpeedSmooth.text())
			except Exception as e:
				pass

			value *= boost
			if value > epsilon:
				value = minv + (maxv - minv) * value
			if value < -epsilon:
				value = -minv + (maxv - minv) * value

			smooth = round(smooth)
			if smooth < 0:
				smooth = 0
			if smooth > 100:
				smooth = 100
			master.lastvals.rotate(1)
			master.lastvals[0] = value
			value = sum(list(itertools.islice(master.lastvals, 0, smooth + 1))) / (smooth + 1)

			slave_nr = master.combo.currentIndex() - 1
			if slave_nr >= 0:
				self.slaves[slave_nr].add_change(value)

		commands = struct.pack('I', self.next_packet_id)
		for slave in self.slaves:
			cmd, axis, val = slave.execute()
			if cmd == MoveCommand.NOP:
				continue

			if axis is None:
				axis = 0
			commands += struct.pack('Bhf', cmd, axis, val)

			# print(cmd, axis, val)

		if len(commands) > 4:
			# print('commands: {}'.format(commands))
			self.cmd_socket.sendto(commands, self.cmd_server_addr)
			self.next_packet_id += 1
	
		self.timer.start(40)