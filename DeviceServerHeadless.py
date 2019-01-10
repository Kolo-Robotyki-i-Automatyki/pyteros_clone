#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 26 09:54:02 2018

This code was originally written by Tomasz Kazimierczuk for LUMS - Laboratory
of Ultrafast MagnetoSpectroscopy at Faculty of Physics, University of Warsaw

"""

from PyQt5 import Qt,QtCore
import time
import zmq
import devices
import sys,traceback



class ZMQ_Listener(QtCore.QObject):
    """ A class to implement a thread listening for stdout/stderr 
    from other thread via a ZeroMQ PUB/SUB socket pair """
    msg_info = QtCore.pyqtSignal(str)
    msg_err = QtCore.pyqtSignal(str)

    def __init__(self, socket):
        QtCore.QObject.__init__(self)
        self.socket = socket
        self.continue_running = True
         
    def loop(self):
        while self.continue_running:
            [address, contents] = self.socket.recv_multipart()
            if address == b'stderr':
                self.msg_err.emit(contents.decode('ascii'))
            else:
                self.msg_info.emit(contents.decode('ascii'))
        print("stopped")


class Process(QtCore.QObject):
    def __init__(self, req_port=0, pub_port=0, process_class = None, **kwargs):
        super().__init__()
        
        self.req_port = req_port
        self.pub_port = pub_port
        self.process_class = process_class
        self.kwargs = kwargs
        
        zmq_context = zmq.Context()
        self.sub_socket = zmq_context.socket(zmq.SUB)
        self.sub_socket.connect("tcp://localhost:%s" % str(pub_port))
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'std')
        
        self.process = None
        
        def appendErr(text):
            print(text)
        
        def appendInfo(text):
            print(text)
            
        self.thread = QtCore.QThread(self)
        self.listener = ZMQ_Listener(self.sub_socket)
        self.listener.moveToThread(self.thread)
        self.thread.started.connect(self.listener.loop)
        self.listener.msg_info.connect(appendInfo)
        self.listener.msg_err.connect(appendErr)
        self.thread.start()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.checkOnProcess)
        self.timer.start(200)

    def __del__(self):
        self.listener.continue_running = False
        if self.process:
            self.process.terminate()
            self.process.join()
            self.process = None

    def createProcess(self):
        return self.process_class(req_port = self.req_port, pub_port = self.pub_port, **self.kwargs)

    def startProcess(self, start = True):
        self.process = self.createProcess()
        self.process.daemon = True
        self.process.start()

    def checkOnProcess(self):
        if self.process == None:
            self.startProcess()

class MainWindow(QtCore.QObject):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.createTabs()

    def createTabs(self):
        workers_desc = devices.load_workers("local_devices_headless.ini")
        self.processes = []
        for name,cls,kwargs in workers_desc:
            try:
                print('creating process')
                process = Process(process_class=cls, **kwargs)
                self.processes.append(process)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)        

if __name__ == '__main__':
    import sys
    def run_app():
        app = QtCore.QCoreApplication(sys.argv)
        window = MainWindow()
        app.exec_()
        
        
    run_app()
