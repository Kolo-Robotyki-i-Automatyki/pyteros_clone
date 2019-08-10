# -*- coding: utf-8 -*-
"""
Created on Sat May 26 09:54:02 2018

This code was originally written by Tomasz Kazimierczuk for LUMS - Laboratory
of Ultrafast MagnetoSpectroscopy at Faculty of Physics, University of Warsaw


"""

from PyQt5 import Qt,QtCore,QtGui,QtWidgets
import time
import devices

class NoRequiredDevicesError(Exception):
    """Error raised if no devices required for given feature is found."""
    pass

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
        self.setGeometry(100, 40, self.width(), 1000)
    
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
        window.show()
        
        devices.load_devices(use_gui=True, parent=window)
        window.kernel_client.execute('import devices')
        window.kernel_client.execute('devices.load_devices()')
        window.kernel_client.execute('globals().update(devices.active_devices)')
        window.kernel_client.execute('print(list(devices.active_devices))')
        window.kernel_client.execute('import time')
        window.kernel_client.execute('import numpy as np')
        
        for _,device in devices.active_devices.items():
            try:
                device.createDock(window, window.controlMenu)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

        try:
            from devices.misc import joystick_control
            w = joystick_control.JoystickControlWidget(devices.active_devices)
            window.addPage(w, "Pad control")
        except NoRequiredDevicesError:
            pass
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            
        '''try:
            from devices.misc import joystick_control2
            w = joystick_control2.JoystickControlWidget(devices.active_devices)
            window.addPage(w, "Pad 2 control")
        except NoRequiredDevicesError:
            pass
        except Exception as e:
            traceback.print_exc(file=sys.stdout)'''
            
        try:
            from src.map_widget_new import map_widget
            w = map_widget.MapWidget(devices.active_devices)
            window.addPage(w, "Map")
        except NoRequiredDevicesError:
            pass
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        try:
            from devices.misc import ik_scripter
            w = ik_scripter.IKScripterWidget(devices.active_devices)
            window.addPage(w, "IK Scripter")
        except NoRequiredDevicesError:
            pass
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        try:
            from src.streaming_widget import streaming_widget
            streaming_widget = streaming_widget.StreamingWidget(devices.active_devices)
            window.addPage(streaming_widget, "Cameras")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        try:
            from src.path_widget import path_widget
            widget = path_widget.PathCreator(devices.active_devices)
            window.addPage(widget, "Autonomy")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

        window.show()
        app.exec_()
                
    run_app()