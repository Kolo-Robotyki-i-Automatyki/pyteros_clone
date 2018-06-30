# -*- coding: utf-8 -*-
"""
Created on Sat May 26 09:54:02 2018

@author: tkaz
"""

from PyQt5 import Qt,QtCore,QtGui,QtWidgets
import time


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.createCentralWidget()
        self.setupIcons()
        
        quitAct = QtWidgets.QAction("&Quit", self);
        quitAct.setShortcuts(QtGui.QKeySequence.Quit)
        quitAct.setStatusTip("Quit the application")
        quitAct.triggered.connect(self.close)
        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addAction(quitAct)        
        self.controlMenu = self.menuBar().addMenu("&Devices")
    
    
    def createConsoleTab(self):
        """ Initialize a python console and return its widget """
        from qtconsole.rich_jupyter_widget import RichJupyterWidget
        from qtconsole.manager import QtKernelManager

        kernel_manager = QtKernelManager(kernel_name='python3')
        kernel_manager.start_kernel()
        kernel = kernel_manager.kernel
        kernel.gui = 'qt'

        kernel_client = kernel_manager.client()
        kernel_client.start_channels()
        kernel_client.namespace  = self

        def stop():
            kernel_client.stop_channels()
            kernel_manager.shutdown_kernel()

        widget = RichJupyterWidget(parent=self)
        widget.kernel_manager = kernel_manager
        widget.kernel_client = kernel_client
        widget.exit_requested.connect(stop)
        ipython_widget = widget
        ipython_widget.show()
        self.kernel_client = kernel_client
        
        return widget
    
    def createProcessControlTab(self):
        """ Creates and returns the widget to control slave processes """
        scrollArea = QtWidgets.QScrollArea()
        self.
        scrollArea.setWidget(widget)
        
    
    
    def addPage(self, widget, name):
        self.tabWidget.addTab(widget, name)
    
    def createCentralWidget(self):
        self.tabWidget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabWidget)
        self.tabWidget.addTab(self.createConsoleTab(), "Console")
        self.tabWidget.addTab(self.createProcessControlTab, "Devices")
        

    def setupIcons(self):
        self.trayIconMenu = QtWidgets.QMenu(self);
        showAction = self.trayIconMenu.addAction("Show main window")
        showAction.triggered.connect(self.show)

        icon = QtGui.QIcon("img/icon_control.svg")
        self.setWindowIcon(icon)
        self.setWindowTitle("pyLUMS - Interactive control")

    

if __name__ == '__main__':
    import sys
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = MainWindow()
        
        workers = []
        frontends = []
        
        try:
            from devices.attocube.anc350 import ANC350
            worker = ANC350Worker(req_port=7000, pub_port=7001)
            workers.append(worker)
            worker.start()
            a = ANC350(req_port=7000, pub_port=7001)
            a.createDock(window, window.controlMenu)
            frontends.append(a)
            #window.kernel_client.execute("from devices.attocube.anc350 import ANC350")
            #window.kernel_client.execute("anc350 = ANC350(req_port=7000, pub_port=7001)")
        except:
            print("Failed to load driver for Attocube ANC350")
            
        try:
            from devices.misc.xbox import XBoxPad,XBoxWorker
            worker = XBoxWorker(req_port=7005, pub_port=7006)
            worker.start()
            workers.append(worker)
            x = XBoxPad(req_port=7005, pub_port=7006)
            x.createDock(window, window.controlMenu)
            frontends.append(x)
            #window.kernel_client.execute("from devices.attocube.anc350 import ANC350")
            #window.kernel_client.execute("anc350 = ANC350(req_port=7000, pub_port=7001)")
        except:
            print("Failed to load driver for Attocube ANC350")
            
        window.show()
        app.exec_()
        
        for w in workers:
            w.terminate()
        for w in workers:
            w.join()
        
    run_app()