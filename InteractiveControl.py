# -*- coding: utf-8 -*-
"""
Created on Sat May 26 09:54:02 2018

@author: tkaz
"""

from PyQt5 import Qt,QtCore,QtGui,QtWidgets
import time
import devices


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
        #kernel_client.execute("import devices.demo.demo")
        return widget
    
    #def createProcessControlTab(self):
        #""" Creates and returns the widget to control slave processes """
        #scrollArea = QtWidgets.QScrollArea()
        #scrollArea.setWidget(widget)
        
    
    
    def addPage(self, widget, name):
        self.tabWidget.addTab(widget, name)
    
    def createCentralWidget(self):
        self.tabWidget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabWidget)
        self.tabWidget.addTab(self.createConsoleTab(), "Console")
        #self.tabWidget.addTab(self.createProcessControlTab, "Devices")
        

    def setupIcons(self):
        self.trayIconMenu = QtWidgets.QMenu(self);
        showAction = self.trayIconMenu.addAction("Show main window")
        showAction.triggered.connect(self.show)

        icon = QtGui.QIcon("img/icon_control.svg")
        self.setWindowIcon(icon)
        self.setWindowTitle("pyLUMS - Interactive control")

    

if __name__ == '__main__':
    import sys,traceback
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = MainWindow()
        
        devices.load_devices()
        window.kernel_client.execute('import devices')
        window.kernel_client.execute('devices.load_devices()')
        window.kernel_client.execute('globals().update(devices.active_devices)')
        window.kernel_client.execute('print(list(devices.active_devices))')
        
        for _,device in devices.active_devices.items():
            try:
                device.createDock(window, window.controlMenu)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

        try:
            from devices.misc import joystick_control
            w = joystick_control.JoystickControlWidget(devices.active_devices)
            window.addPage(w, "Pad control")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            
        try:
            from src import map_widget
            w = map_widget.MapWidget(devices.active_devices)
            window.addPage(w, "Map")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        
        try:
            from src import tab_anisotropy
            w = tab_anisotropy.AnisotropyTab()
            window.addPage(w, "Anisotropy")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
                
                
        window.show()
        app.exec_()
                
    run_app()