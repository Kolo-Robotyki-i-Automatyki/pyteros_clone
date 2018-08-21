from PyQt5 import QtWidgets, QtCore

from devices.zeromq_device import DeviceWorker, DeviceOverZeroMQ, remote, include_remote_methods
from PyQt5 import QtWidgets, QtCore, QtGui
import time

import os

NO_OF_AXES = 4

default_req_port = 7006
default_pub_port = 7007


class DummyANC350Worker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        self.rate = 0.04
        super().__init__(req_port=req_port, pub_port=pub_port, refresh_rate=self.rate)
        self.connected = False

    def loop(self):
        for i in range(NO_OF_AXES):
            self.position[i] += 0.04 * self.frequency[i] * self.moving[i] * self.direction[i]

    def status(self):
        self.loop()
        d = super().status()
        d["connected"] = self.connected
        for i in self.axes():
            d["axis%d_pos" % i] = self.axisPos(i)
        return d

    def init_device(self):
        print("init_device")
        # self.timer = QtCore.QTimer()
        # self.timer.setInterval(50)
        # self.timer.timeout.connect(self.loop)
        # self.timer.start()
        if self.connected:
            return
        self.connected = True
        self.position = [2000, 2000, 2000, 2000]
        self.frequency = [0, 0, 0, 0]
        self.direction = [1, 1, 1, 1]
        self.moving = [0, 0, 0, 0]
        self.axesList = [0, 1, 2, 3]
        print("Following dummy axes are now enabled: ", self.axes())

    def axes(self):
        return self.axesList

    def disconnect(self):
        return 1

    def enableAxis(self, axis):
        return 1

    def disableAxis(self, axis):
        return 1

    def moveSteps(self, axis, steps):
        """Number of steps can be positive or negative"""
        s = 1 if steps > 0 else -1
        for i in range(abs(steps)):
            self.position[axis] += 0.63 * s
            time.sleep(0.01)

    def moveAbsolute(self, axis, target, wait=False):
        self.position[axis] = target
        self.moving[axis] = 0

    def stopMovement(self, axis):
        self.moving[axis] = 0

    def moveVelocity(self, axis, frequency):
        if frequency == 0:
            self.stopMovement(axis)
            return
        if frequency < 0:
            frequency = -frequency
            self.direction[axis] = -1
        else:
            self.direction[axis] = 1
        self.setFrequency(axis, frequency)
        self.moving[axis] = 1

    def setFrequency(self, axis, frequency):
        self.frequency[axis] = frequency

    def moveContinous(self, axis, dir):
        self.direction[axis] = 1 - 2 * dir
        self.moving[axis] = 1

    def stopMovement(self, axis):
        self.moving[axis] = 0

    def axisPos(self, axis):
        return self.position[axis]

    def axisStatus(self, axis):
        return 1


if __name__ == '__main__':
    import sys


    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = QtWidgets.QMainWindow()
        window.show()
        app.exec_()


    run_app()