# -*- coding: utf-8 -*-
"""
"""

import os
from PyQt5 import QtCore,QtWidgets,QtGui
import PyQt5
import jsonpickle
import time
from DeviceServerHeadless import get_devices, get_proxy
from ..rover import Rover

dead_zone = 0.15

class IKScripterWidget(QtWidgets.QWidget):
    """ A widget for interactive control of APT motors or attocube axes using XBoxPad """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_list = { dev.name: get_proxy(dev) for dev in get_devices() }
        self.rover = None
        try:
            for rovername, rover in {k: v for k, v in self.device_list.items() if isinstance(v, Rover)}.items():
                self.rover = rover
                break
        except Exception as e:
            print(e)
        #if self.rover == None:
        #    from src.measurement_tab import NoRequiredDevicesError
        #    raise NoRequiredDevicesError("No rover found")

        self._createWidgets()

        self.files = []
        self.indexes = {}
        self.load_filenames()
        self.list_files.currentItemChanged.connect(self.load_file)
        self.button_save.pressed.connect(self.save_file)
        self.button_refresh.pressed.connect(self.load_filenames)
        self.button_run.pressed.connect(self.run)
        self.button_abort.pressed.connect(self.abort)

    def _createWidgets(self):
        widget1 = QtWidgets.QWidget()
        layout1 = QtWidgets.QHBoxLayout(widget1)
        widget2 = QtWidgets.QWidget()
        layout2 = QtWidgets.QHBoxLayout(widget2)
        widget22 = QtWidgets.QWidget()
        layout22 = QtWidgets.QVBoxLayout(widget22)
        layout22.setContentsMargins(0, 0, 0, 0)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(widget1)
        layout.addWidget(widget2)
        self.setLayout(layout)

        self.edit_name = QtWidgets.QLineEdit()
        layout1.addWidget(self.edit_name)
        self.button_refresh = QtWidgets.QPushButton("Refresh")
        layout1.addWidget(self.button_refresh)
        self.button_save = QtWidgets.QPushButton("Save")
        layout1.addWidget(self.button_save)
        self.button_run = QtWidgets.QPushButton("Run")
        layout1.addWidget(self.button_run)
        self.button_abort = QtWidgets.QPushButton("Abort")
        layout1.addWidget(self.button_abort)

        self.edit_code = QtWidgets.QPlainTextEdit()
        layout2.addWidget(self.edit_code)
        self.list_files = QtWidgets.QListWidget()
        layout2.addWidget(widget22)
        layout22.addWidget(self.list_files)
        layout22.addWidget(QtWidgets.QLabel('To Define axis name  write name and motor\n' +
                                            'number in separate line, f. eg.: "clamp 193".\n' +
                                            'Otherwise begin script line with time to wait\n'
                                            'AFTER line execution.\n' +
                                            'Next, in the same line write arbitrary number of\n' +
                                            'commands, each of one of several types:\n\n'
                                            '<motor number> <power>\n' +
                                            'f. eg. : "193 -0.5" or "clamp -0.5".\n\n' +
                                            'Another type is for inverse kinematics:\n' +
                                            'x <arm_lower> <arm_upper> <gripper_lat> <arm_rot>\n' +
                                            'a <arm_h> <arm_v> <gripper_lat> <arm_rot>\n' +
                                            'r <x> <y> <z> <gripper_lat>\n\n' +
                                            'Dimensions are specified in degrees or milimeters.'))

    def load_filenames(self):
        if len(self.files) > 0:
            last_file = self.files[self.list_files.currentIndex().row()]
        else:
            last_file = None
        self.list_files.clear()
        datadir = QtCore.QDir.current()
        datadir.cd("scripts")
        file_list = datadir.entryList()
        self.files = []
        self.indexes = {}
        programs = {}
        for file in file_list[2:]:
            print(file)
            if file[-4:] != '.txt':
                continue
            name = file[0:-4]
            try:
                f = open("scripts" + os.sep + name + ".txt", "r")
                text = f.read()
                programs[name] = text
            except Exception as e:
                print(e)
            self.indexes[name] = len(self.files)
            self.files.append(name)
            self.list_files.addItem(name)
        self.rover.update_script_library(programs)
        if last_file != None:
            self.list_files.setCurrentIndex(self.list_files.currentIndex().sibling(self.indexes[last_file], 0))

    def load_file(self):
        name = self.files[self.list_files.currentIndex().row()]
        self.save_file()
        self.edit_name.setText(name)
        file = open("scripts" + os.sep + name + ".txt", "r")
        text = file.read()
        self.edit_code.setPlainText(text)

    def save_file(self):
        if self.edit_name.text() == "":
            return
        name = self.edit_name.text()
        file = open("scripts" + os.sep + name + ".txt", "w")
        file.write(self.edit_code.toPlainText())
        self.load_filenames()
        self.list_files.setCurrentIndex(self.list_files.currentIndex().sibling(self.indexes[name], 0))

    def run(self):
        code = self.edit_code.toPlainText()
        self.rover.run_script(code)

    def abort(self):
        self.rover.abort_script()
