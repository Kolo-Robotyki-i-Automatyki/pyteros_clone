from datetime import datetime
import time
from time import sleep
from time import perf_counter as clock
import visa
import threading
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets, QtCore, QtGui


default_req_port = 7031
default_pub_port = 7032

class IPS120Worker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, address="COM1", isobus="None", **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

        self._address = address
        self._isobus = isobus

        if isobus != "None":
            self.isobus_header = '@%s' % self._isobus
        else:
            self._isobus_header = ''

        self._target_field = 0
        self._persistent_after = False
        self._stage = None
        self._goal_time = clock()

    def status(self):
        d = super().status()
        d["busy"] = self.busy()
        d["field"] = self.field()
        d["setpoint"] = self.setpoint()
        d["power_supply_field"] = self.power_supply_field()
        return d

    def init_device(self):
        """
        Opens the communication and starts the polling thread for IPS
        """
        self.visa_lock = threading.Lock()
        self.procedure_lock = threading.Lock()
        rm = visa.ResourceManager()
        if self._address[0:3] == 'COM':
            self.visa_handle = rm.open_resource("ASRL%s::INSTR" % self._address[3:])
            self.visa_handle.set_visa_attribute(visa.constants.VI_ATTR_ASRL_STOP_BITS,
                                                visa.constants.VI_ASRL_STOP_TWO)
        else:
            self.visa_handle = rm.open_resource("GPIB::%s" % self._address[4:])

        self.visa_handle.read_termination = '\r'
        self.set_remote()
        self._execute("M9") # set display to tesla
        self.continue_running = True
        self.ips_thread = threading.Thread(target=self._procedure_loop)
        self.ips_thread.start()
        print("Success")

    def _read(self):
        # because protocol has no termination chars the read reads the number
        # of bytes in the buffer
        bytes_in_buffer = self.visa_handle.bytes_in_buffer
        # a workaround for a timeout error in the pyvsia read_raw() function
        with(self.visa_handle.ignore_warning(visa.constants.VI_SUCCESS_MAX_CNT)):
            mes = self.visa_handle.visalib.read(
                self.visa_handle.session, bytes_in_buffer)
        # cannot be done on same line for some reason
        mes = str(mes[0].decode())
        return mes

    def _execute(self, message):
        with self.visa_lock:
            self.visa_handle.write(self.isobus_header + message)
            sleep(70e-3)  # wait for the device to be able to respond
            result = self._read()

        if result.find('?') >= 0:
            print("Error: Command %s not recognized: %s" % (message, result))
            return None
        else:
            return result

    def close_device(self):
        self.continue_running = False
        self.ips_thread.join()

    def _procedure_loop(self):
        while self.continue_running:
            self._procedure_iteration()
            sleep(0.1)

    def _procedure_iteration(self):
        with self.procedure_lock:
            if self._stage == 0: # in case of brutal cancelation of piervous procedure wait for heater state to settle
                if clock() >= self._goal_time:
                    self._stage = 1
            if self._stage == 1: # set power supply output to field inside magnet, if necessary
                self.set_remote()
                magnet_field = self.field()
                if magnet_field == self.power_supply_field():
                    self._stage = 3
                else :
                    self.set_setpoint(magnet_field)
                    self.go_to_setpoint()
                    self._stage = 2
            if self._stage == 2: # wait for power supply oputput to reach field inside magnet
                if self.power_supply_field() == self.setpoint():
                    self._stage = 3
            if self._stage == 3: # turn on heater, if necessary
                if self.heater():
                    self._stage = 5
                else:
                    self.set_heater(True)
                    self._goal_time = clock() + 20
                    self._stage = 4
            if self._stage == 4: # wait 20s for heater to turn on
                if clock() >= self._goal_time:
                    self._stage = 5
            if self._stage == 5: # go to target field
                self.set_setpoint(self._target_field)
                self._stage = 6
            if self._stage == 6: # waiting for field to reach target, next turn heater off if set persistent is on
                if self.power_supply_field() == self.setpoint():
                    if self._persistent_after:
                        self.set_heater(False)
                        self._goal_time = clock() + 20
                        self._stage = 7
                    else:
                        self._stage = None
            if self._stage == 7: # wait 20s for heater to turn off, then go to zero
                if clock() >= self._goal_time:
                    self.go_to_zero()
                    self._stage = None


    @remote
    def busy(self):
        return self._stage != None and self._stage < 7

    @remote
    def set_remote(self):
        self._execute("C3")

    @remote
    def field(self):
        if self.heater():
            return self.power_supply_field()
        else:
            return self.persistent_field()

    @remote
    def set_field(self, target_field=0, persistent_after=False):
        with self.procedure_lock:
            self._persistent_after = persistent_after
            self._target_field = target_field
            self._stage = 0

    @remote
    def setpoint(self):
        return float(self._execute('R8')[1:])

    @remote
    def set_setpoint(self, field):
        self._execute("J{}".format(field))

    @remote
    def power_supply_field(self):
        return float(self._execute('R7')[1:])

    @remote
    def persistent_field(self):
        return float(self._execute('R18')[1:])

    @remote
    def field_sweep_rate(self):
        return float(self._execute('R9')[1:])

    @remote
    def set_field_sweep_rate(self, rate):
        self._execute("T{}".format(rate))

    @remote
    def go_to_zero(self):
        self._execute("A2")

    @remote
    def go_to_setpoint(self):
        self._execute("A1")

    @remote
    def set_hold(self):
        self._execute("A0")

    @remote
    def heater(self):
        status = self._execute("X")
        if status != None:
            if len(status) == 16:
                return status[8] == "1"
    @remote
    def set_heater(self, state=1):
        self._execute("H{}".format(int(state)))

@include_remote_methods(IPS120Worker)
class IPS120(DeviceOverZeroMQ):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)

    def __del__(self):
        pass

    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Magnet IPS120", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QGridLayout(parentWidget)
        layout.setSpacing(2)
        widget.setLayout(layout)
        self.label_field = QtWidgets.QLineEdit()
        self.label_power_supply_field = QtWidgets.QLineEdit()
        self.label_setpoint = QtWidgets.QLineEdit()
        self.label_field.setEnabled(False)
        self.label_power_supply_field.setEnabled(False)
        self.label_setpoint.setEnabled(False)
        self.check_persistent = QtWidgets.QCheckBox("Set persistent afterwards")
        self.edit_field = QtWidgets.QLineEdit()
        self.edit_field.setValidator(QtGui.QDoubleValidator())
        self.edit_field.returnPressed.connect(self.set_field_clicked)
        self.button_set_field = QtWidgets.QPushButton("Set Field")
        self.button_set_field.clicked.connect(self.set_field_clicked)

        layout.addWidget(QtWidgets.QLabel("Field in magnet:"), 1, 1)
        layout.addWidget(QtWidgets.QLabel("Power supply output:"), 2, 1)
        layout.addWidget(QtWidgets.QLabel("Setpoint:"), 3, 1)
        layout.addWidget(self.label_field, 1, 2)
        layout.addWidget(self.label_power_supply_field, 2, 2)
        layout.addWidget(self.label_setpoint, 3, 2)
        layout.addWidget(self.check_persistent, 4, 1, 1, 2)
        layout.addWidget(self.edit_field, 5, 1)
        layout.addWidget(self.button_set_field, 5, 2)

        dock.setWidget(widget)

        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())

        self.createListenerThread(self.updateSlot)

    def set_field_clicked(self):
        try:
            target = float(self.edit_field.text())
            self.set_field(target, self.check_persistent.isChecked())
        except Exception:
            print("invalid target field value")

    def updateSlot(self, status):
        self.label_field.setText("%2.4f T" % status["field"])
        self.label_power_supply_field.setText("%2.4f T" % status["power_supply_field"])
        self.label_setpoint.setText("%2.4f T" % status["setpoint"])

