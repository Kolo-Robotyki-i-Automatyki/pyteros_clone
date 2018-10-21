# -*- coding: utf-8 -*-

from time import sleep
import threading
from inputs import devices
from ..zeromq_device import DeviceWorker, DeviceOverZeroMQ, remote, include_remote_methods

default_req_port = 7004
default_pub_port = 7005


class XBoxWorker(DeviceWorker):

    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, id=0, **kwargs):
        self.device_number = int(id)
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

        self.axes = {
            'ABS_X': 'l_thumb_x',
            'ABS_Y': 'l_thumb_y',
            'ABS_RX': 'r_thumb_x',
            'ABS_RY': 'r_thumb_y',
            'ABS_Z': 'left_trigger',
            'ABS_RZ': 'right_trigger',
            'ABS_HAT0X': 'button4',
            'ABS_HAT0Y': 'button1',
            'BTN_SELECT': 'button5',
            'BTN_START': 'button6',
            'BTN_THUMBL': 'button7',
            'BTN_THUMBR': 'button8',
            'BTN_NORTH': 'button16',
            'BTN_SOUTH': 'button13',
            'BTN_EAST': 'button14',
            'BTN_WEST': 'button15',
            'BTN_TL': 'button9',
            'BTN_TR': 'button10'}

        self.values = {}
        for axis in self.axes:
            self.values[axis] = 0

    def init_device(self):
        self.gamepad = devices.gamepads[self.device_number]
        try:
            self.gamepad.set_vibration(1, 1)
            sleep(0.5)
            self.gamepad.set_vibration(0, 0)
        except Exception:
            pass



        print("Pad no. " + str(self.device_number + 1) + " is now connected.")
        self.state_lock = threading.Lock()
        self.status_thread = threading.Thread(target=self._state_loop)
        self.status_thread.start()

    def _state_loop(self):
        while True:
            try:
                events = self.gamepad.read()
                for event in events:
                    if event.ev_type in  ['Absolute', 'Key']:
                        axis = event.code
                        value = event.state
                        if axis in ['ABS_X', 'ABS_Y', 'ABS_RX', 'ABS_RY']:
                            value = value / 2 ** 15
                        if axis in ['ABS_Z', 'ABS_RZ']:
                            value = value / 2 ** 8
                        if axis in ['ABS_HAT0Y']:
                            value = -value
                        with self.state_lock:
                            self.values[axis] = value
            except Exception as e:
                for key in self.values:
                    with self.state_lock:
                        self.values[key] = 0
                with self.state_lock:
                    self.values["connected"] = False

    def get_state(self):
        with self.state_lock:
            state = self.values
        ret = {}
        for axis in self.axes:
            ret[self.axes[axis]] = state[axis]
        return ret

    @remote
    def set_vibration(self, left_motor, right_motor):
        self.gamepad.set_vibration(left_motor, right_motor)

    def status(self):
        d = super().status()

        state = self.get_state()

        if not state:
            d['connected'] = False
            return d
        else:
            d['connected'] = True

        for axis in state:
            d[axis] = state[axis]

        return d

    @remote
    def currentStatus(self):
        return self.status()


@include_remote_methods(XBoxWorker)
class XBoxPad(DeviceOverZeroMQ):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

    def createDock(self, parentWidget, menu=None):
        from PyQt5 import QtWidgets, QtCore

        dock = QtWidgets.QDockWidget("XBox pad", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        widget.setLayout(layout)
        self.checkbox = QtWidgets.QCheckBox('Connected')
        self.checkbox.setDisabled(True)
        self.checkbox.setTristate(True)
        self.checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
        layout.addWidget(self.checkbox)
        # self.textedit = QtWidgets.QTextEdit()
        # layout.addWidget(self.textedit)

        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())

        def updateSlot(status):
            if 'connected' in status:
                v = QtCore.Qt.Checked if status['connected'] else QtCore.Qt.Unchecked
                self.checkbox.setCheckState(v)
            # self.textedit.setText(str(status))

        self.createListenerThread(updateSlot)
