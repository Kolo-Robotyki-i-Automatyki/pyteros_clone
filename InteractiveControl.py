# -*- coding: utf-8 -*-
"""
Created on Sat May 26 09:54:02 2018

This code was originally written by Tomasz Kazimierczuk for LUMS - Laboratory
of Ultrafast MagnetoSpectroscopy at Faculty of Physics, University of Warsaw


"""

from PyQt5 import Qt, QtCore, QtGui, QtWidgets

from DeviceServerHeadless import DeviceServer, DeviceType, DeviceServerWrapper
from src.common.misc import create_obj_from_path

import importlib
import sys
import threading
import time
import traceback
import zmq


PAGES = {
    'Devices': 'src.devices_widget.devices_widget.DevicesWidget',
    'Pad control': 'devices.misc.joystick_control.JoystickControlWidget',
    'Control config': 'src.control_widget.control_widget_new.ControlConfigWidget',
    # 'Pad 2 control': 'devices.misc.joystic_control2.JoystickControlWidget',
    'Map': 'src.map_widget.map_widget.MapWidget',
    'Map [new]': 'src.map_widget_new.map_widget.MapWidget',
    'IK Scripter': 'devices.misc.ik_scripter.IKScripterWidget',
    'Cameras': 'src.streaming_widget.streaming_widget.StreamingWidget',
}


class RestartAction(QtWidgets.QAction):
    def __init__(self, page_name, window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_name = page_name
        self.window = window
        self.setText(page_name)
        self.triggered.connect(self._restart_page)

    def _restart_page(self):
        self.window.restart_page(self.page_name)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.zmq_context = zmq.Context()

        self.device_server = DeviceServerWrapper(self.zmq_context)

        self.createCentralWidget()
        self.setupIcons()

        self.tabs = {}
        
        quitAct = QtWidgets.QAction("&Quit", self);
        quitAct.setShortcuts(QtGui.QKeySequence.Quit)
        quitAct.setStatusTip("Quit the application")
        quitAct.triggered.connect(self.close)
        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addAction(quitAct)

        pages_menu = self.menuBar().addMenu('Restart')
        for page_name in PAGES:
            restart_act = RestartAction(page_name=page_name, window=self, parent=self)
            pages_menu.addAction(restart_act)

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
        return widget

    def restart_page(self, page_name):
        prev_idx = self.tabWidget.count()
        for i in range(self.tabWidget.count()):
            if self.tabWidget.tabText(i) == page_name:
                prev_idx = i
                self.tabWidget.removeTab(i)
                break

        try:
            class_path = PAGES[page_name]
            tab_widget = create_obj_from_path(class_path, self.device_server)
        except Exception as e:
            error_msg = traceback.format_exc()
            tab_widget = QtWidgets.QLabel(error_msg)
            tab_widget.setStyleSheet('QLabel { color : red; }')
    
        self.tabWidget.insertTab(prev_idx, tab_widget, page_name)    

    def createCentralWidget(self):
        self.tabWidget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabWidget)
        self.tabWidget.addTab(self.createConsoleTab(), "Console")

    def setupIcons(self):
        self.trayIconMenu = QtWidgets.QMenu(self);
        showAction = self.trayIconMenu.addAction("Show main window")
        showAction.triggered.connect(self.show)

        icon = QtGui.QIcon("img/icon_control.svg")
        self.setWindowIcon(icon)
        self.setWindowTitle("pyLUMS - Interactive control")



if __name__ == '__main__':
    def run_app():
        app = QtWidgets.QApplication(sys.argv)
        window = MainWindow()
        window.show()
        
        window.kernel_client.execute('import time')
        window.kernel_client.execute('import numpy as np')
        window.kernel_client.execute('import zmq')
        window.kernel_client.execute('ctx = zmq.Context()')
        window.kernel_client.execute('from DeviceServerHeadless import *')
        window.kernel_client.execute('device_server = DeviceServerWrapper(ctx)')
        
        # device_server = DeviceServer()
        # try:
        #     for dev in device_server.devices():
        #         try:
        #             interface = dev.interface()
        #             interface.createDock(window, window.controlMenu)
        #         except Exception as e:
        #             traceback.print_exc(file=sys.stdout)
        # except:
        #     traceback.print_exc()

        for page_name in PAGES:
            try:
                window.restart_page(page_name)
            except:
                print('[InteractiveControl] when restarting {}'.format(page_name))
                traceback.print_exc()

        window.show()
        app.exec_()
                
    run_app()
