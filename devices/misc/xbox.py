# -*- coding: utf-8 -*-

#!/usr/bin/env python

"""
A module for getting input from Microsoft XBox 360 controllers via the XInput library on Windows.
Adapted from Jason R. Coombs' code here:
http://pydoc.net/Python/jaraco.input/1.0.1/jaraco.input.win32.xinput/
under the MIT licence terms
Upgraded to Python 3
Modified to add deadzones, reduce noise, and support vibration
Only req is Pyglet 1.2alpha1 or higher:
pip install --upgrade http://pyglet.googlecode.com/archive/tip.zip 
"""

import ctypes
import sys
import math
import time
from operator import itemgetter, attrgetter
from itertools import count
import json

from ..zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler

# structs according to
# http://msdn.microsoft.com/en-gb/library/windows/desktop/ee417001%28v=vs.85%29.aspx


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ('buttons', ctypes.c_ushort),  # wButtons
        ('left_trigger', ctypes.c_ubyte),  # bLeftTrigger
        ('right_trigger', ctypes.c_ubyte),  # bLeftTrigger
        ('l_thumb_x', ctypes.c_short),  # sThumbLX
        ('l_thumb_y', ctypes.c_short),  # sThumbLY
        ('r_thumb_x', ctypes.c_short),  # sThumbRx
        ('r_thumb_y', ctypes.c_short),  # sThumbRy
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ('packet_number', ctypes.c_ulong),  # dwPacketNumber
        ('gamepad', XINPUT_GAMEPAD),  # Gamepad
    ]


class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [("wLeftMotorSpeed", ctypes.c_ushort),
                ("wRightMotorSpeed", ctypes.c_ushort)]

class XINPUT_BATTERY_INFORMATION(ctypes.Structure):
    _fields_ = [("BatteryType", ctypes.c_ubyte),
                ("BatteryLevel", ctypes.c_ubyte)]

try:
    xinput = ctypes.windll.xinput1_3
except:
    xinput = ctypes.windll.xinput9_1_0  # this is the Win 8 version ?

# xinput1_2, xinput1_1 (32-bit Vista SP1)
# xinput1_3 (64-bit Vista SP1)


def struct_dict(struct):
    """
    take a ctypes.Structure and return its field/value pairs
    as a dict.
    >>> 'buttons' in struct_dict(XINPUT_GAMEPAD)
    True
    >>> struct_dict(XINPUT_GAMEPAD)['buttons'].__class__.__name__
    'CField'
    """
    get_pair = lambda field_type: (
        field_type[0], getattr(struct, field_type[0]))
    return dict(list(map(get_pair, struct._fields_)))


def get_bit_values(number, size=32):
    """
    Get bit values as a list for a given number
    >>> get_bit_values(1) == [0]*31 + [1]
    True
    >>> get_bit_values(0xDEADBEEF)
    [1L, 1L, 0L, 1L, 1L, 1L, 1L, 0L, 1L, 0L, 1L, 0L, 1L, 1L, 0L, 1L, 1L, 0L, 1L, 1L, 1L, 1L, 1L, 0L, 1L, 1L, 1L, 0L, 1L, 1L, 1L, 1L]
    You may override the default word size of 32-bits to match your actual
    application.
    >>> get_bit_values(0x3, 2)
    [1L, 1L]
    >>> get_bit_values(0x3, 4)
    [0L, 0L, 1L, 1L]
    """
    res = list(gen_bit_values(number))
    res.reverse()
    # 0-pad the most significant bit
    res = [0] * (size - len(res)) + res
    return res


def gen_bit_values(number):
    """
    Return a zero or one for each bit of a numeric value up to the most
    significant 1 bit, beginning with the least significant bit.
    """
    number = int(number)
    while number:
        yield number & 0x1
        number >>= 1

ERROR_DEVICE_NOT_CONNECTED = 1167
ERROR_SUCCESS = 0


default_req_port = 7004
default_pub_port = 7005


class XBoxWorker(DeviceWorker):

    def __init__(self, req_port = default_req_port, pub_port = default_pub_port, **kwargs):
        self.device_number = 0
        super().__init__(req_port = req_port, pub_port = pub_port, **kwargs)

        self._last_state = self.get_state()
        self.received_packets = 0
        self.missed_packets = 0

        # Set the method that will be called to normalize
        #  the values for analog axis.
        choices = [self.translate_identity, self.translate_using_data_size]
        self.translate = choices[True]

    def init_device(self):
        battery = self.get_battery_information()
        print(battery)

    def translate_using_data_size(self, value, data_size):
        # normalizes analog data to [0,1] for unsigned data
        #  and [-0.5,0.5] for signed data
        data_bits = 8 * data_size
        return float(value) / (2 ** data_bits - 1)

    def translate_identity(self, value, data_size=None):
        return value

    def get_state(self):
        "Get the state of the controller represented by this object"
        state = XINPUT_STATE()
        res = xinput.XInputGetState(self.device_number, ctypes.byref(state))
        if res == ERROR_SUCCESS:
            return state
        if res != ERROR_DEVICE_NOT_CONNECTED:
            raise RuntimeError(
                "Unknown error %d attempting to get state of device %d" % (res, self.device_number))
        # else return None (device is not connected)

    @handler("XBox", "isConnected")
    def is_connected(self):
        return self._last_state is not None

    @handler("XBox", "setVibration")
    def set_vibration(self, left_motor, right_motor):
        "Control the speed of both motors seperately"
        # Set up function argument types and return type
        XInputSetState = xinput.XInputSetState
        XInputSetState.argtypes = [ctypes.c_uint, ctypes.POINTER(XINPUT_VIBRATION)]
        XInputSetState.restype = ctypes.c_uint

        vibration = XINPUT_VIBRATION(
            int(left_motor * 65535), int(right_motor * 65535))
        XInputSetState(self.device_number, ctypes.byref(vibration))

    def get_battery_information(self):
        "Get battery type & charge level"
        BATTERY_DEVTYPE_GAMEPAD = 0x00
        BATTERY_DEVTYPE_HEADSET = 0x01
        # Set up function argument types and return type
        XInputGetBatteryInformation = xinput.XInputGetBatteryInformation
        XInputGetBatteryInformation.argtypes = [ctypes.c_uint, ctypes.c_ubyte, ctypes.POINTER(XINPUT_BATTERY_INFORMATION)]
        XInputGetBatteryInformation.restype = ctypes.c_uint

        battery = XINPUT_BATTERY_INFORMATION(0,0)
        XInputGetBatteryInformation(self.device_number, BATTERY_DEVTYPE_GAMEPAD, ctypes.byref(battery))

        #define BATTERY_TYPE_DISCONNECTED       0x00
        #define BATTERY_TYPE_WIRED              0x01
        #define BATTERY_TYPE_ALKALINE           0x02
        #define BATTERY_TYPE_NIMH               0x03
        #define BATTERY_TYPE_UNKNOWN            0xFF
        #define BATTERY_LEVEL_EMPTY             0x00
        #define BATTERY_LEVEL_LOW               0x01
        #define BATTERY_LEVEL_MEDIUM            0x02
        #define BATTERY_LEVEL_FULL              0x03
        batt_type = "Unknown" if battery.BatteryType == 0xFF else ["Disconnected", "Wired", "Alkaline","Nimh"][battery.BatteryType]
        level = ["Empty", "Low", "Medium", "Full"][battery.BatteryLevel]
        return batt_type, level


    def update_packet_count(self, state):
        "Keep track of received and missed packets for performance tuning"
        self.received_packets += 1
        missed_packets = state.packet_number - \
            self._last_state.packet_number - 1
        if missed_packets:
            pass
        self.missed_packets += missed_packets

    def status(self):
        d = super().status()

        state = self.get_state()

        if not state:
            d['connected'] = False
            return d
            #raise RuntimeError(
            #    "Joystick %d is not connected" % self.device_number)
        d['connected'] = True
        if state.packet_number != self._last_state.packet_number:
            self.update_packet_count(state)

        axis_fields = dict(XINPUT_GAMEPAD._fields_)

        axis_fields.pop('buttons')
        for axis, type in list(axis_fields.items()):
            old_val = getattr(self._last_state.gamepad, axis)
            new_val = getattr(state.gamepad, axis)
            data_size = ctypes.sizeof(type)
            old_val = self.translate(old_val, data_size)
            new_val = self.translate(new_val, data_size)

            # an attempt to add deadzones and dampen noise
            # done by feel rather than following http://msdn.microsoft.com/en-gb/library/windows/desktop/ee417001%28v=vs.85%29.aspx#dead_zone
            # ags, 2014-07-01
            #if ((old_val != new_val and (new_val > 0.08000000000000000 or new_val < -0.08000000000000000) and abs(old_val - new_val) > 0.00000000500000000) or
            #   (axis == 'right_trigger' or axis == 'left_trigger') and new_val == 0 and abs(old_val - new_val) > 0.00000000500000000):
            #    d[axis] = new_val:
            d[axis] = new_val


        changed = state.gamepad.buttons ^ self._last_state.gamepad.buttons
        changed = get_bit_values(changed, 16)
        buttons_state = get_bit_values(state.gamepad.buttons, 16)
        changed.reverse()
        buttons_state.reverse()
        button_numbers = count(1)
        for c,n,s in zip(changed, button_numbers, buttons_state):
            d["button%d" % n] = s

        self._last_state = state
        return d

    @handler("XBox", "currentStatus")
    def currentStatus(self):
        return self.status()


def sample_first_joystick():
    """
    Grab 1st available gamepad, logging changes to the screen.
    L & R analogue triggers set the vibration motor speed.
    """
    joysticks = XInputJoystick.enumerate_devices()
    device_numbers = list(map(attrgetter('device_number'), joysticks))

    print('found %d devices: %s' % (len(joysticks), device_numbers))

    if not joysticks:
        sys.exit(0)

    j = joysticks[0]
    print('using %d' % j.device_number)

    battery = j.get_battery_information()
    print(battery)

    def on_button(button, pressed):
        print('button', button, pressed)

    left_speed = 0
    right_speed = 0

    def on_axis(axis, value):
        left_speed = 0
        right_speed = 0

        print('axis', axis, value)
        if axis == "left_trigger":
            left_speed = value
        elif axis == "right_trigger":
            right_speed = value
        j.set_vibration(left_speed, right_speed)




class XBoxPad(DeviceOverZeroMQ):
    def __init__(self, req_port = default_req_port, pub_port = default_pub_port, **kwargs):
        super().__init__(req_port = req_port, pub_port = pub_port, **kwargs)
        self.createDelegatedMethods("XBox")


    def createDock(self, parentWidget, menu = None):
        from PyQt5 import QtWidgets,QtCore
        
        dock = QtWidgets.QDockWidget("XBox pad", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        widget.setLayout(layout)
        self.checkbox = QtWidgets.QCheckBox('Connected')
        self.checkbox.setDisabled(True)
        self.checkbox.setTristate(True)
        self.checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
        layout.addWidget(self.checkbox)
        #self.textedit = QtWidgets.QTextEdit()
        #layout.addWidget(self.textedit)
        
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
        
        def updateSlot(status):
            if 'connected' in status:
                v = QtCore.Qt.Checked if status['connected'] else QtCore.Qt.Unchecked
                self.checkbox.setCheckState(v)
            #self.textedit.setText(str(status))
        
        self.createListenerThread(updateSlot)
