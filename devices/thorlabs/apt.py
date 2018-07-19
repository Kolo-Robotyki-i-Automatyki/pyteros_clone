# -*- coding: utf-8 -*-


from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,handler
from PyQt5 import QtWidgets,QtCore
import time

default_req_port = 7008
default_pub_port = 7009

class APTWorker(DeviceWorker):
    """ Class managing all Thorlabs APT  motor controllers """
    
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.motors = {}
        
    def init_device(self):
        from . import apt_wrapper
        serials = [n for (t,n) in apt_wrapper.list_available_devices()]
        print("%d APT devices found" % len(serials))
        for n in serials:
            print("SN: %d" % n)
            mot = apt_wrapper.Motor(n)
            mot.initial_parameters = mot.get_velocity_parameters()
            mot.prev_request_time = time.time()
            self.motors[n] = mot
        
    min_request_delay = 0.05
    
    def wait(self, motor):
        now = time.time()
        elapsed = now - motor.prev_request_time
        if elapsed > 0 and elapsed < self.min_request_delay:
            time.sleep(self.min_request_delay - elapsed)
        motor.prev_request_time = now
    
    def status(self):
        d = super().status()
        d["apt_devices"] = self.devices()
        for sn in self.motors:
            motor = self.motors[sn]
            self.wait(motor)
            d["apt_%d" % sn] = \
                {"position": motor.position,
                 "stopped":  motor.is_in_motion }
        return d
    
    @handler("APT", "moveTo")
    def moveTo(self, serial, target):
        mot = self.motors[serial]
        self.wait(mot)
        mot.set_velocity_parameters(*mot.initial_parameters)
        mot.move_to(target)
        
    @handler("APT", "devices")
    def devices(self):
        return [sn for sn in self.motors]
    
    @handler("APT", "moveVelocity")
    def moveVelocity(self, serial, velocity):
        if velocity == 0:
            return self.stop(serial)
        """ velocity should be between -1 to 1 """
        mot = self.motors[serial]
        self.wait(mot)
        param = mot.initial_parameters[:2]+(abs(velocity)*mot.initial_parameters[2],)
        mot.set_velocity_parameters(*param)
        direction = 1 if velocity > 0 else 2
        mot.move_velocity(direction)
        
    @handler("APT", "stop")
    def stop(self, serial):
        mot = self.motors[serial]
        self.wait(mot)
        mot.set_velocity_parameters(*mot.initial_parameters)
        mot.stop_profiled()
    
    @handler("APT", "position")
    def position(self, serial):
        mot = self.motors[serial]
        self.wait(mot)
        return mot.position
    


class APT(DeviceOverZeroMQ):   
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.createDelegatedMethods("APT")
        # custom initialization here
        self.widgets = {}
        
        
    def createDock(self, parentWidget, menu=None):
        """ Function for integration in GUI app.  """
        dock = QtWidgets.QDockWidget("Thorlabs APT", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        self.layout = QtWidgets.QVBoxLayout(parentWidget)
        widget.setLayout(self.layout)
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
        
        self.createListenerThread(self.updateSlot)



    def appendRow(self, serial):
        hlayout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("s/n: %d" % serial)
        hlayout.addWidget(label)
        display = QtWidgets.QLCDNumber()
        display.setSegmentStyle(QtWidgets.QLCDNumber.Flat)
        display.setDigitCount(5)
        display.display("0.0")
        
        hlayout.addWidget(display)
        hlayout.addStretch(3)
        self.layout.addLayout(hlayout)
        self.widgets[serial] = (display,)
        
        def on_click(event):
            if event.button() == 1:
                current = self.position(serial)
                d, okPressed = QtWidgets.QInputDialog.getDouble(display, "Go to","Target:", current, 0, 360)
                if okPressed:
                    self.moveTo(serial, d)
        display.mousePressEvent  = on_click            
        
        
    def updateSlot(self, status):
        for serial in status["apt_devices"]:
            if serial not in self.widgets:
                self.appendRow(serial)
            motor_status = status["apt_%d" % serial]
            self.widgets[serial][0].display("%.1f" % motor_status["position"])

    
