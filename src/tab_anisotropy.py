# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets
import devices
from devices.thorlabs import apt

from measurement_tab import MeasurementThread, MeasurementTab, NoRequiredDevicesError        


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
            raise NoRequiredDevicesError("No APT found")
                
        
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