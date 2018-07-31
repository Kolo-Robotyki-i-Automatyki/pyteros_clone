# -*- coding: utf-8 -*-
import scipy as sp
from PyQt5 import QtWidgets,QtGui,QtCore
import time
import devices
from devices.thorlabs import apt


class MeasurementThread(QtCore.QThread):
    measurement_progress = QtCore.pyqtSignal(int)
    estimated_time = QtCore.pyqtSignal(float)
    measurement_info = QtCore.pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancelled = False
        self.paused = False
    
    def check_if_cancel_requested(self):
        """ Call this function periodically to enable user to pause or cancel
        the measurement """
        if self.paused:
            self.log("Paused")
            while self.paused:
                time.sleep(0.5)
                if self.cancelled:
                    return
        else:
            if self.cancelled:
                raise Exception("Thread cancelled")
    
    def wait_for_condition(self, func):
        """ Call this function to wait for certain condition (e.g., until 
        motor reaches its destination) while checking for pause or cancel """
        self.check_if_cancel_requested()
        while not func():
            self.check_if_cancel_requested()
            time.sleep(0.2)
    
    def log(self, msg):
        """ Call this function instead of print """
        self.measurement_info.emit(str(msg))
        print(msg)
    
    def run(self):
        """ You should override this method in subclass """
        try:
            for i in range(10):
                self.check_if_cancel_requested()
                time.sleep(1)
                self.log("Step %d" %i)
                self.measurement_progress.emit(i)
        except:
            pass

    

class MeasurementTab(QtWidgets.QWidget):
    def __init__(self, thread_class=MeasurementThread, parent=None):
        super().__init__(parent)
        self.thread = thread_class(self)
        self.thread.finished.connect(self.thread_stopped)
        self.setup_ui()
        
    def setup_additional_widgets(self, layout):
        pass
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.setup_additional_widgets(layout)
        self.log_widget = QtWidgets.QTextEdit()
        self.log_widget.setReadOnly(True)
        self.thread.measurement_info.connect(self.log_widget.append)
        layout.addWidget(self.log_widget)
        button_box = QtWidgets.QDialogButtonBox()
        self.start_button = QtWidgets.QPushButton("Start")
        button_box.addButton(self.start_button, QtWidgets.QDialogButtonBox.AcceptRole)
        self.start_button.clicked.connect(self.start)
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause)
        self.pause_button.setEnabled(False)
        self.pause_button.setCheckable(True)
        button_box.addButton(self.pause_button, QtWidgets.QDialogButtonBox.NoRole)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        button_box.addButton(self.cancel_button, QtWidgets.QDialogButtonBox.RejectRole)
        layout.addWidget(button_box)
        
        hlayout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()       
        self.progress_bar.setValue(0)
        self.thread.measurement_progress.connect(self.progress_bar.setValue)
        hlayout.addWidget(self.progress_bar)
        self.remaining_time_label = QtWidgets.QLabel()
        self.remaining_time_label.setMinimumWidth(100)
        self.remaining_time_label.setMaximumWidth(100)
        hlayout.addWidget(self.remaining_time_label)
        layout.addLayout(hlayout)
        
    def start(self):
        self.prepare_thread_for_running()
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.thread.paused = self.pause_button.isChecked()
        self.thread.cancelled = False
        self.log_widget.clear()
        self.log_widget.setTextColor(QtGui.QColor(255,0,0))
        self.log_widget.append("Starting")
        self.log_widget.setTextColor(QtGui.QColor(0,0,0))
        self.progress_bar.setValue(0)
        self.thread.start()
        
    def cancel(self):
        self.thread.cancelled = True
        self.cancel_button.setText("Canceling")
    
    def pause(self, activate):
        self.log_widget.setTextColor(QtGui.QColor(255,0,0))
        self.log_widget.append("Requesting pause" if activate else "Resuming")
        self.log_widget.setTextColor(QtGui.QColor(0,0,0))
        self.thread.paused = activate
        
    def prepare_thread_for_running(self):
        pass
    
    def thread_stopped(self):
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setChecked(False)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancel")
        self.progress_bar.setValue(0)
        self.log_widget.setTextColor(QtGui.QColor(255,0,0))
        self.log_widget.append("Finished")
        self.log_widget.setTextColor(QtGui.QColor(0,0,0))
        


from numpy import linspace

class AnisotropyThread(MeasurementThread):
    def run(self):
        try:
            positions = linspace(self.pos1, self.pos2, self.steps)
            for n,pos in enumerate(positions):
                self.apt.moveTo(pos)
                self.wait_for_condition(self.apt.isStopped)            
        except Exception as e:
            self.log(e)
    

class AnisotropyTab(MeasurementTab):
    def __init__(self):
        super().__init__(thread_class=AnisotropyThread)
        self.__known_stages = set()
        
        found = False
        for _,device in devices.active_devices.items():
            if isinstance(device, apt.APT):
                device.createListenerThread(self.__monitor_for_new_apt_stages)
                found = True
        if not found:
            raise Exception("No APT found")
                
        
    def setup_additional_widgets(self, layout):
        formlayout = QtWidgets.QFormLayout()
        
        hlayout = QtWidgets.QHBoxLayout()
        self.file_input = QtWidgets.QLineEdit()
        hlayout.addWidget(self.file_input, 4)
        button = QtWidgets.QPushButton("Browse")
        def browse_for_file():
            file = QtWidgets.QFileDialog.getSaveFileName(self,
                            "Save file as", self.file_input.text(),
                            "HDF5 file (*.hd5)")
            if file[0]:
                self.file_input.setText(file[0])
        button.clicked.connect(browse_for_file)   
        hlayout.addWidget(button)
        formlayout.addRow("File name: ", hlayout)
        
        self.range_combo = QtWidgets.QComboBox()
        self.range_combo.addItem("0°-90°", (0,90))
        self.range_combo.addItem("0°-180°", (0,180))
        self.range_combo.addItem("0°-360°", (0,360))
        self.range_combo.setCurrentIndex(1)
        formlayout.addRow("Range of angles:", self.range_combo)
        
        self.steps_input = QtWidgets.QSpinBox()
        self.steps_input.setMinimum(2)
        self.steps_input.setValue(45)
        self.steps_input.setMaximum(10000)
        formlayout.addRow("Steps:", self.steps_input)
        
        self.axis_input = QtWidgets.QComboBox()
        formlayout.addRow("Motor:", self.axis_input)
        
        layout.addLayout(formlayout)
    
    def prepare_thread_for_running(self):
        self.file_input.setEnabled(False)
        self.range_combo.setEnabled(False)
        self.steps_input.setEnabled(False)
        self.axis_input.setEnabled(False)
    
    def thread_stopped(self):
        super().thread_stopped()
        self.file_input.setEnabled(True)
        self.range_combo.setEnabled(True)
        self.steps_input.setEnabled(True)
        self.axis_input.setEnabled(True)

    def __refresh_combo(self):
        current_axis = self.axis_input.currentText()
        
        param_list = []
        for _,device in devices.active_devices.items():
            if isinstance(device, apt.APT):
                param_list.extend(device.get_parameters())
        current_axis = self.axis_input.currentText()
        for param in param_list:
            self.axis_input.addItem(param.name(), param)
        self.axis_input.setCurrentText(current_axis)
        
    def __monitor_for_new_apt_stages(self, msg):
        stages = set([name for name in msg if name.startswith('apt_')])
        if not stages.issubset(self.__known_stages):
            self.__known_stages = self.__known_stages | stages
            self.__refresh_combo()
    
if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    okno = AnisotropyTab([])
    okno.show()
    sys.exit(app.exec_())