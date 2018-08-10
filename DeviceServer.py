# -*- coding: utf-8 -*-
"""
Created on Sat May 26 09:54:02 2018

@author: tkaz
"""

from PyQt5 import Qt,QtCore,QtGui,QtWidgets
import time
from devices.demo.demo import WorkerForDummyDevice
import zmq


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




class WidgetForProcess(QtWidgets.QWidget):
    def __init__(self, req_port, pub_port, process_class = WorkerForDummyDevice):
        super().__init__()
        
        self.req_port = req_port
        self.pub_port = pub_port
        self.process_class = process_class
        
        zmq_context = zmq.Context()
        self.sub_socket = zmq_context.socket(zmq.SUB)
        self.sub_socket.connect("tcp://localhost:%d" % pub_port)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'std')
        
        self.process = None
        
        layout = QtWidgets.QVBoxLayout()
        layout2 = QtWidgets.QHBoxLayout()
        label1 = QtWidgets.QLabel("REQ port:")
        edit1 = QtWidgets.QLineEdit(str(self.req_port))
        edit1.setEnabled(False)
        layout2.addWidget(label1)
        layout2.addWidget(edit1)
        layout2.addSpacing(10)
        label2 = QtWidgets.QLabel("PUB port:")
        edit2 = QtWidgets.QLineEdit(str(self.pub_port))
        edit2.setEnabled(False)
        layout2.addWidget(label2)
        layout2.addWidget(edit2)
        layout2.addSpacing(10)
        self.startbutton = QtWidgets.QPushButton("Start process")
        self.startbutton.setCheckable(True)
        self.startbutton.clicked.connect(self.startProcess)
        layout2.addWidget(self.startbutton)
        layout2.addStretch(5)
        layout.addLayout(layout2)
        textedit = QtWidgets.QTextEdit()
        textedit.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(textedit)
        self.setLayout(layout)
        
        def appendErr(text):
            textedit.setTextColor(QtGui.QColor(255,0,0))
            textedit.append(text)
        
        def appendInfo(text):
            textedit.setTextColor(QtGui.QColor(0,0,64))
            textedit.append(text)
            
        self.thread = QtCore.QThread(self)
        self.listener = ZMQ_Listener(self.sub_socket)
        self.listener.moveToThread(self.thread)
        self.thread.started.connect(self.listener.loop)
        self.listener.msg_info.connect(appendInfo)
        self.listener.msg_err.connect(appendErr)
        self.thread.start()
        layout.addWidget(textedit)
        
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.checkOnProcess)
        self.timer.start(5000)
        
    def __del__(self):
        self.listener.continue_running = False
        if self.process:
            self.process.terminate()
            self.process.join()
            self.process = None

    def createProcess(self):
        return self.process_class(req_port = self.req_port, pub_port = self.pub_port)

    def startProcess(self, start = True):
        if start:
            self.process = self.createProcess()
            self.process.daemon = True
            self.process.start()
            self.startbutton.setChecked(True)
        else:
            if self.process:
                self.process.terminate()
                self.process.join()
                self.process = None


    def checkOnProcess(self):
        if self.process == None:
            self.startbutton.setChecked(False)
            return
        if self.process.is_alive():
            self.startbutton.setChecked(True)
        elif self.process.exitcode is None: # Not finished and not running
            # Do your error handling and restarting here assigning the new process to processes[n]
            self.startbutton.setChecked(False)
            self.process = None
        elif self.process.exitcode < 0:
            self.startbutton.setChecked(False)
            self.process = None
        else:
            print ('finished')
            self.process.join()
            self.process = None



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.createCentralWidget()
        self.setupIcons()

        quitAct = QtWidgets.QAction("&Quit", self);
        quitAct.setShortcuts(QtGui.QKeySequence.Quit)
        quitAct.setStatusTip("Quit the application")
        quitAct.triggered.connect(self.close)
        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addAction(quitAct)
        self.createTabs()

    def createCentralWidget(self):
        self.toolBox = QtWidgets.QToolBox()
        self.setCentralWidget(self.toolBox)

    def setupIcons(self):
        self.trayIconMenu = QtWidgets.QMenu(self);
        showAction = self.trayIconMenu.addAction("Show main window")
        showAction.triggered.connect(self.show)

        icon = QtGui.QIcon("img/icon_server.svg")
        self.setWindowIcon(icon)
        self.setWindowTitle("pyLUMS - Device server")


    def createTabs(self):

        try:
            from devices.attocube import dummyanc350 as anc350
            widget = WidgetForProcess(pub_port = anc350.default_pub_port,
                                      req_port = anc350.default_req_port,
                                      process_class = anc350.ANC350Worker)
            self.toolBox.addItem(widget, "ANC350")
        except Exception as e:
            print(str(e))

        try:
            from devices.misc import xbox
            widget = WidgetForProcess(pub_port = xbox.default_pub_port,
                                      req_port = xbox.default_req_port,
                                      process_class = xbox.XBoxWorker)
            self.toolBox.addItem(widget, "XBox pad")
        except Exception as e:
            print(str(e))

        #try:
        #    from devices.misc.xbox import XBoxPad,XBoxWorker
        #    widget = WidgetForProcess(pub_port=6998,
        #                              req_port=6999,
        #                              process_class=WorkerForDummyDevice)
        #    self.toolBox.addItem(widget, "Demo")
        #except Exception as e:
        #    print(str(e))

        try:
            from devices.thorlabs import apt
            widget = WidgetForProcess(pub_port = apt.default_pub_port,
                                      req_port = apt.default_req_port,
                                      process_class = apt.APTWorker)
            self.toolBox.addItem(widget, "Thorlabs APT")
        except Exception as e:
            print(str(e))
        


if __name__ == '__main__':
    import sys
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        icon = QtGui.QIcon("img/icon_server.svg")
        app.setWindowIcon(icon)
        window = MainWindow()
        
        window.show()
        app.exec_()
        
        
    run_app()