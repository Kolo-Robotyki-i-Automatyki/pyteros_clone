# -*- coding: utf-8 -*-
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets,QtCore
from PyQt5.QtWidgets import (QPushButton, QMessageBox, QDialog)
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow)
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLineEdit)
from PyQt5.QtWidgets import (QLabel, QInputDialog)
from PyQt5.QtGui import (QFont, QColor)

class TiSapphireWorker(DeviceWorker):
    '''The class contains every methods needed to talk to the motor'''
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def init_device(self):
        import serial
        self.ser = serial.Serial('COM3', 9600, timeout=5)  #opens serial port COM3
        
    def __del__(self):
        self.ser.close() #serial port close
        
    def status(self):
        """ This function will be called periodically to monitor the state 
        of the device. It should return a dictionary describing the current
        state of the device. This dictionary will be delivered to the 
        front-end class."""
        d = super().status()
        d["connected"] = True
        d["voltage"] = self.voltage
        print(d)
        return d

        
    @remote
    def sf(self):
        '''Method sets motor fixing at 0'''
        self.ser.write(b'sf0\n')
        
    @remote
    def tf(self):
        '''Method returns current fixing'''
        self.ser.write(b'tf\n')
        self.response = self.ser.readline()
        return self.response

    @remote
    def goto(self, position):
        '''Motor moves to absolute position which is the method argument'''
        self.ser.write(b'ma' + str(position).encode('ascii') + b'\n')
        
    @remote
    def whereareyou(self):
        '''Method returns current absolute position of the motor'''
        self.ser.write(b'tp\n')
        self.ret = self.ser.readline()
        return self.ret
    
@include_remote_methods(TiSapphireWorker)
class TiSapphire(DeviceOverZeroMQ):  
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
               
    def createDock(self, parentWidget, menu=None):
        """ Function for integration in GUI app. Implementation below 
        creates a button and a display """
        dock = QtWidgets.QDockWidget("Ti:Sapphire laser", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        self.initUI(widget, self)
        
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
            
        # Following lines "turn on" the widget operation
        self.createListenerThread(self.updateSlot)

        
    def updateSlot(self, status):
        pass
    
    def initUI(self, widget, motor):
        title = '<center><h2>Hello!<\h2><\center>'
        intro = '<center><font-size = "14">My name is titanium-sapphire laser.<br> I am able to emit light of 710-800 nm. <br> Press start to commence our adventure.<br><\font>'

        self.title = QLabel(title)
        self.intro = QLabel(intro)        
        
        self.font = QFont()
        self.font.setPointSize(10)
        self.intro.setFont(self.font)
        
        tell_position_btn = QPushButton('Position', self)
        tell_position_btn.resize(tell_position_btn.sizeHint())
        tell_position_btn.setStyleSheet("background-color:rgb(210, 242, 223)")
        tell_position_btn.clicked.connect(self.position_window)
        
        start_btn = QPushButton('Start', self)
        start_btn.resize(start_btn.sizeHint())
        start_btn.setStyleSheet("background-color:rgb(252, 227, 244)")
        start_btn.clicked.connect(self.wavelength_window)
        
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(start_btn)
        hlayout.addWidget(tell_position_btn)
        vlayout.addWidget(self.title)
        vlayout.addWidget(self.intro)
        vlayout.addLayout(hlayout)
        widget.setLayout(vlayout)
          
        widget.setAutoFillBackground(True)
        p = widget.palette()
        p.setColor(self.backgroundRole(), QColor(220, 229, 228))
        widget.setPalette(p)
        
    def position_window(self):
        '''This method opens the window of class Tell_Position which contains current position of the motor'''
        self.window = Tell_Position(self)
        self.window.show()

    def wavelength_window(self):
        '''This method opens the window of class Wavelength where user enters expected wavelength. 
        In case of any problem with motor power after last use, the programm shows warning window of class
        Warn'''
        self.motor = motor
        if self.motor.tf() == b'TF64\r\n':
            self.alarm = Warn(self)
            self.alarm.exec_()
        else:
            self.window2 = Wavelength(self)
            self.window2.show()
            
            
class Warn(QDialog):
    def __init__(self, motor):
        super().__init__()
        self.motor = motor
        self.initUI()
        
        
    def initUI(self):
        '''Window with caution and a button'''
        caution = QLabel('<h1><p style="color:red">CAUTION<\h1>!', self)
        text = QLabel('<center>Recently I went out of power!<br> Make sure the screw position is 5,810. <br>', self)
        text.move(20, 80)
        caution.move(90, 20)
        
        self.ready_btn = QPushButton('Ready', self)
        self.ready_btn.move(20, 20)
        self.ready_btn.clicked.connect(self.ready_button_pressed)
        self.ready_btn.move(90, 120)
        
        self.setGeometry(300, 300, 300, 200)
        self.setWindowTitle('WARNING')
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(255, 255, 255))
        self.setPalette(p)
        self.move(500, 250)
        self.show()
            
    def ready_button_pressed(self):
        '''Method which automatically opens a window to enter wavelength after pressing ready button'''
        motor.sf()
        self.close()
        self.window2 = Wavelength(self.motor)
        self.window2.show()
        
class Wavelength(QWidget):
    def __init__(self, motor):
        super().__init__()
        self.motor = motor
        self.initUI(motor)
        
        
    def initUI(self, motor):      
        '''Window of enternig wavelength and a button go'''
        self.enter_wavelngth_btn = QPushButton('Wavelength', self)
        self.enter_wavelngth_btn.move(20, 20)
        self.enter_wavelngth_btn.setStyleSheet("background-color:rgb(252, 227, 244)")
        self.enter_wavelngth_btn.clicked.connect(self.showDialog)
        
        self.go_btn = QPushButton('Go', self)
        self.go_btn.move(188, 50)
        self.go_btn.setStyleSheet("background-color:rgb(210, 242, 223)")
        self.go_btn.clicked.connect(self.go_button_pressed)
        
        self.le = QLineEdit(self) #possible entering wavelength in line edit or after pressing enter_wavelngth_btn
        self.le.move(130, 22)
        
        self.setGeometry(300, 300, 290, 150)
        self.setWindowTitle('Enter wavelength')
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(220, 229, 228))
        self.setPalette(p)
        self.move(200, 250)
        self.show()
        
    def go_button_pressed(self):
        '''When go button is pressed the method call the function goto of class Motor. 
        Respects only entered values from 700 to 810 nm''' 
        text = self.le.text()
        self.wavelength = str(text)
        if float(text) < 700:
            self.wavelength = 700
        if float(text) > 810:
            self.wavelength = 810
        self.motor_position = 3.81136 * pow(10,7)-153870.05478 * float(self.wavelength) +209.32328*float(self.wavelength)*float(self.wavelength)-0.096*float(self.wavelength)*float(self.wavelength)*float(self.wavelength)
        self.motor.goto(self.motor_position)
        
        
    def showDialog(self):
        '''Additional window with exact command to enter wavelength. Opens after pressing enter_wavelngth_btn
        '''
        text, ok = QInputDialog.getText(self, 'Settings', 
            'Enter wavelength:')
        
        if ok:
            self.le.setText(str(text))
            
class Tell_Position(QWidget):
    def __init__(self, motor):
        super().__init__()
        self.motor = motor
        self.initUI(motor)
        
        
    def initUI(self, motor):
        '''Position parameters shown. Calculates using motor position thanks to function whereareyou'''
        self.motor_position_answer = str(motor.whereareyou())
        self.motor_position = self.motor_position_answer[4:-5]
        self.wavelength = 724.617 - 6.01328 * float(self.motor_position) * pow(10, -4) -9.10299 * float(self.motor_position) * float(self.motor_position) * pow(10, -10)
        self.screw = -860.06621 + 3.49860397 * float(self.wavelength) - 0.004764992 * float(self.wavelength) * float(self.wavelength) + 2.18853868 * float(self.wavelength) * float(self.wavelength) * float(self.wavelength) * pow(10, -6)
        
        lbl1 = QLabel('<h4>Your current position:<\h4>', self)
        lbl1.move(20, 10)
        
        lbl2 = QLabel('Wavelength   ' + str(round(float(self.wavelength), 1)), self)
        lbl2.move(20, 30)
        
        lbl3 = QLabel('Screw   ' + str(round(float(self.screw), 3)), self)
        lbl3.move(20, 50)     
        
        lbl4 = QLabel('Motor absolute position  ' + str(self.motor_position), self)
        lbl4.move(20, 70) 
        
        self.setGeometry(300, 300, 250, 150)
        self.setWindowTitle('Position')
        self.move(800, 250)
        self.show()