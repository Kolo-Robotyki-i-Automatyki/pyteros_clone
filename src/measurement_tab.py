# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets,QtGui,QtCore

class NoRequiredDevicesError(Exception):
    """Error raised if no devices required for given feature is found."""
    pass

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

