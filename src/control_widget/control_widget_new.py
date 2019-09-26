import enum
import queue
import threading
import time
import traceback

from PyQt5 import QtGui, QtWidgets, QtCore

from DeviceServerHeadless import DeviceType
from devices.rover import MoveCommand
from ..common.settings import Settings


REFRESH_DELAY_MS = 100
DEVICE_DISCOVERY_PERIOD_S = 1.0

AXES_NAMES = [
    ("l_thumb_x", "Left stick horizontal"),
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
    ("alt_button15", "Alt X button")
]


RequestType = enum.Enum('RequestType', [
    'find_motors',
    'configure_control',
    'start_control',
    'stop_control',
])

class ControlConfigWidget(QtWidgets.QWidget):
    """ A widget for interactive control of APT motors or attocube axes using XBoxPad """

    def __init__(self, device_server, parent=None):
        super().__init__(parent)

        self.lock = threading.Lock()

        self.device_server = device_server

        self.requests_queue = queue.SimpleQueue()
        self.motors_queue = queue.SimpleQueue()
        self.control_status_queue = queue.SimpleQueue()

        self.rover = None
        self.control = None

        self.control_is_running = False

        self.gamepad_axes = AXES_NAMES

        self.settings = Settings('joystick_control')

        self.config_rows = []
        self.motors = []

        self._createWidgets()

        self.requests_queue = queue.SimpleQueue()
        threading.Thread(target=self._process_requests, daemon=True).start()
        threading.Thread(target=self._detect_devices, daemon=True).start()

        self.refresh_timer = QtCore.QTimer()
        self.refresh_timer.setInterval(REFRESH_DELAY_MS)
        self.refresh_timer.timeout.connect(self._refresh)
        self.refresh_timer.start()

    def _refresh(self):
        self._refresh_combos()
        self._refresh_buttons()

    def _refresh_combos(self):
        motors = None
        while True:
            try:
                motors = self.motors_queue.get_nowait()
            except queue.Empty:
                break
        if motors is None:
            return

        with self.lock:
            self.motors = motors

            for _, combo, _, _, _, _ in self.config_rows:
                combo.clear()
                combo.addItem('None')
                for description, _, _ in motors:
                    combo.addItem(description)

            self.combos_widget.setEnabled(True)

    def _refresh_buttons(self):
        status = None
        while True:
            try:
                status = self.control_status_queue.get_nowait()
            except queue.Empty:
                break
        if status is None:
            return

        self.control_is_running = status.get('is_running')
        self.startButton.setText('Stop control' if self.control_is_running else 'Start control')
        self.startButton.setEnabled(True)

    def _process_requests(self):
        while True:
            request = self.requests_queue.get()
            request_type = request[0]

            # Requests to the rover
            try:
                if request_type == RequestType.find_motors:
                    rover = self.rover
                    if rover is None:
                        return

                    motors = []

                    motors.append(('turning right', MoveCommand.DRIVE, 1))
                    motors.append(('throttle', MoveCommand.DRIVE, 0))
                    for name, id in rover.axes():
                        description = name + "(" + str(id) + ")"
                        motors.append((description, MoveCommand.POWER, id))
                    for name, id in rover.servos():
                        description = name + "(" + str(id) + ")"
                        motors.append((description, MoveCommand.SERVO, id))

                    self.motors_queue.put(motors)

            except ConnectionError:
                print('[control_config] no connection to the rover')
                with self.lock:
                    rover.close()
                    self.rover = None            
            except:
                traceback.print_exc()

            finally:
                self.combos_widget.setEnabled(True)

            # Requests to the control node
            try:
                if request_type == RequestType.configure_control:
                    control = self.control
                    if control is not None:
                        _, config = request
                        control.configure(config)

                elif request_type == RequestType.start_control:
                    control = self.control
                    if control is not None:
                        control.start_control()

                elif request_type == RequestType.stop_control:
                    control = self.control
                    if control is not None:
                        control.stop_control()

            except ConnectionError:
                print('[config_control] no connection to the control node')
                with self.lock:
                    control.close()
                    self.control = None
            except:
                traceback.print_exc()

    def _detect_devices(self):
        while True:
            try:
                with self.lock:
                    if self.rover is None:
                        self.rover = self.device_server.find_device([DeviceType.rover, DeviceType.fake_rover])
                    if self.control is None:
                        self.control = self.device_server.find_device([DeviceType.control])
                        if self.control is not None:
                            self.control.create_listener_thread(self._process_control_status)
            except:
                traceback.print_exc()

            time.sleep(DEVICE_DISCOVERY_PERIOD_S)

    def _process_control_status(self, control_status):
        self.control_status_queue.put(control_status)

    def _find_motors(self):
        self.combos_widget.setDisabled(True)
        self.requests_queue.put((RequestType.find_motors,))

    def _upload_config(self):
        self.save_settings()

        with self.lock:
            motors = []
            for description, method, axis in self.motors:
                motors.append({
                    'method': method,
                    'axis': axis
                })

            mappings = []
            for axis_id, combo, checkInverted, editSpeedMax, editSpeedMin, editSmooth in self.config_rows:
                motor_id = combo.currentIndex() - 1
                if motor_id < 0:
                    continue
                inverted = checkInverted.isChecked()
                try:
                    minval = float(editSpeedMin.text() or '0.0')
                    maxval = float(editSpeedMax.text() or '1.0')
                    smooth = int(editSmooth.text() or '0')
                except:
                    traceback.print_exc()
                    continue
                mappings.append({
                    'gamepad_axis': axis_id,
                    'motor_id': motor_id,
                    'inverted': inverted,
                    'minval': minval,
                    'maxval': maxval,
                    'smooth': smooth,
                })

        config = {
            'motors': motors,
            'mappings': mappings,
        }

        self.requests_queue.put((RequestType.configure_control, config))

    def _start_or_stop_control(self):
        self.startButton.setDisabled(True)
        if self.control_is_running:
            self.requests_queue.put((RequestType.stop_control,))
        else:
            self.requests_queue.put((RequestType.start_control,))

    def _createWidgets(self):
        with self.lock:
            mainlayout = QtWidgets.QVBoxLayout()
            self.setLayout(mainlayout)

            self.combos_widget = QtWidgets.QWidget()
            gridlayout = QtWidgets.QGridLayout()
            gridlayout.setSpacing(2)
            gridlayout.setColumnStretch(5, 6)
            gridlayout.setRowStretch(len(self.gamepad_axes), 16)
            for row, (axis_id, label) in enumerate(self.gamepad_axes):
                gridlayout.addWidget(QtWidgets.QLabel(label), row, 0)
                combo = QtWidgets.QComboBox()
                combo.addItem("None")
                combo.setMinimumWidth(230)
                gridlayout.addWidget(combo, row, 1)
                gridlayout.addWidget(QtWidgets.QLabel("Inv.:"), row, 2)
                checkInverted = QtWidgets.QCheckBox();
                gridlayout.addWidget(checkInverted, row, 3)
                gridlayout.addWidget(QtWidgets.QLabel("Max:"), row, 4)
                editSpeedMax = QtWidgets.QLineEdit()
                editSpeedMax.setFixedWidth(60)
                editSpeedMax.setValidator(QtGui.QDoubleValidator())
                gridlayout.addWidget(editSpeedMax, row, 5)
                gridlayout.addWidget(QtWidgets.QLabel("Min:"), row, 6)
                editSpeedMin = QtWidgets.QLineEdit()
                editSpeedMin.setFixedWidth(60)
                editSpeedMin.setValidator(QtGui.QDoubleValidator())
                gridlayout.addWidget(editSpeedMin, row, 7)
                gridlayout.addWidget(QtWidgets.QLabel("Smooth:"), row, 8)
                editSpeedSmooth = QtWidgets.QLineEdit()
                editSpeedSmooth.setFixedWidth(60)
                editSpeedSmooth.setValidator(QtGui.QIntValidator())
                gridlayout.addWidget(editSpeedSmooth, row, 9)
                gridlayout.setColumnStretch(10, 10)
                
                self.config_rows.append((axis_id, combo, checkInverted, editSpeedMax, editSpeedMin, editSpeedSmooth))
            self.combos_widget.setLayout(gridlayout)
            mainlayout.addWidget(self.combos_widget)

            mainlayout.addStretch()

            controllayout = QtWidgets.QHBoxLayout()
            self.refreshButton = QtWidgets.QPushButton('Refresh motors')
            self.refreshButton.clicked.connect(self._find_motors)
            controllayout.addWidget(self.refreshButton)
            self.controlConfigButton = QtWidgets.QPushButton('Upload config')
            self.controlConfigButton.clicked.connect(self._upload_config)
            # self.controlConfigButton.clicked.connect(self.save_settings)
            controllayout.addWidget(self.controlConfigButton)
            mainlayout.addLayout(controllayout, 0)

            buttonlayout = QtWidgets.QHBoxLayout()
            self.loadButton = QtWidgets.QPushButton('Load settings')
            self.loadButton.clicked.connect(self.load_settings)
            buttonlayout.addWidget(self.loadButton)
            self.startButton = QtWidgets.QPushButton('Start control')
            self.startButton.setCheckable(True)
            self.startButton.clicked.connect(self._start_or_stop_control)
            # self.startButton.clicked.connect(self.save_settings)
            buttonlayout.addWidget(self.startButton)
            mainlayout.addLayout(buttonlayout)

    def load_settings(self):
        motors = self.settings.get('motors') or []
        mappings = self.settings.get('mappings') or []

        self.motors = motors
        for (current_index, inverted, minval, maxval, smooth), config_row in zip(mappings, self.config_rows):
            _, combo, checkInverted, editSpeedMax, editSpeedMin, editSmooth = config_row
            combo.clear()
            combo.addItem('None')
            for description, _, _ in motors:
                combo.addItem(description)
            combo.setCurrentIndex(current_index)
            checkInverted.setChecked(inverted)
            editSpeedMin.setText(str(minval))
            editSpeedMax.setText(str(maxval))
            editSmooth.setText(str(smooth))

    def save_settings(self):
        motors = self.motors
        mappings = []
        for _, combo, checkInverted, editSpeedMax, editSpeedMin, editSmooth in self.config_rows:
            current_index = combo.currentIndex()
            inverted = checkInverted.isChecked()
            minval = float(editSpeedMin.text() or '0.0')
            maxval = float(editSpeedMax.text() or '1.0')
            smooth = int(editSmooth.text() or '0')
            mappings.append((current_index, inverted, minval, maxval, smooth))

        self.settings.set('motors', motors, save=False)
        self.settings.set('mappings', mappings, save=False)
        self.settings.save()
