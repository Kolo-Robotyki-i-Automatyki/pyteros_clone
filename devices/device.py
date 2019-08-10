'''# -*- coding: utf-8 -*-

This code was originally written by Tomasz Kazimierczuk for LUMS - Laboratory
of Ultrafast MagnetoSpectroscopy at Faculty of Physics, University of Warsaw

'''
from enum import Enum
from numpy import nan
import yaml

from src.common.settings import Settings


class Device:
    """ A prototype of a class representing a single device, 
    e.g. a positioner or a spectrometer """
    def __init__(self, **kwargs):
        self.priority = Device.Priority.Normal
        
    class Priority(Enum):
        Critical = 1 # Experiment is stopped if device fails
        Semicritical = 2 # Experiment is stopped if a request fails
        Normal = 3 # Experiment is resumed when communication is restored
        Optional = 4 # Experiment continoues even if device fails
    
    def name(self):
        return type(self).__name__
    
    def status(self):
        return {}


class Parameter:
    """ A prototype of a class representing a single parameter in the experiment.
    This class is introduced to provide a uniform interface for control widgets.
    E.g., a single multi-axis controller Device can provide several Parameters
    representing single axes."""
    def name(self):
        raise NotImplementedError
    
    def value(self):
        raise NotImplementedError
    
    def move_to_target(self, target):
        raise NotImplementedError
    
    def move_continuous(self, value):
        raise NotImplementedError
    
    def is_moving(self):
        raise NotImplementedError


""" A dictionary of loaded devices. Key is the interpreter name of the object """
active_devices = {}


import importlib
import sys,traceback


""" Enabled devices """
dev_launch_settings = Settings('devices')


def load_devices(use_gui=False, parent=None, file='devices.yaml'):
    with open(file, 'r') as config_file:
        config = yaml.load(config_file, Loader=yaml.SafeLoader)
   
    if use_gui:
        from PyQt5 import QtWidgets

        dialog = QtWidgets.QDialog(parent)
        dialog.setWindowTitle("Select devices")
        layout = QtWidgets.QVBoxLayout()
        dialog.setLayout(layout)

        checkboxes = {}

        for dev, dev_conf in config.items():
            checkbox = QtWidgets.QCheckBox(dev_conf['name'])
            enabled = dev_launch_settings.get(dev, False)
            checkbox.setChecked(enabled)
            checkboxes[dev] = checkbox
            layout.addWidget(checkbox)

        buttonbox = QtWidgets.QDialogButtonBox()
        buttonbox.addButton("Start", QtWidgets.QDialogButtonBox.AcceptRole)
        buttonbox.accepted.connect(dialog.accept)
        layout.addWidget(buttonbox)
        
        _ = dialog.exec_()
        for dev in config.keys():
            enabled = checkboxes[dev].isChecked()
            dev_launch_settings.set(dev, enabled, save=False)
        dev_launch_settings.save()
    
    for dev, dev_conf in config.items():
        if dev_launch_settings.get(dev, False):
            try:
                host = dev_conf['host']
                req = dev_conf['req_port']
                pub = dev_conf['pub_port']

                kwargs = {
                    'host': host,
                    'req_port': req,
                    'pub_port': pub,
                }

                module_name, class_name = dev_conf['client_class'].rsplit('.', 1)
                DeviceClass = getattr(importlib.import_module('devices.'+module_name), class_name)
                instance = DeviceClass(**kwargs)

                active_devices[dev] = instance
            except Exception as e:
                print("Loading device {} failed.".format(dev))
                traceback.print_exc(file=sys.stdout)


def load_workers(file='devices.yaml', hostname='localhost'):
    with open(file, 'r') as config_file:
        config = yaml.load(config_file, Loader=yaml.SafeLoader)
   
    workers = []

    for dev, dev_conf in config.items():
        try:
            if dev_conf['host'] != hostname:
                continue

            name = dev_conf['name']
            host = dev_conf['host']
            req = dev_conf['req_port']
            pub = dev_conf['pub_port']

            kwargs = {
                'req_port': req,
                'pub_port': pub,
            }
            kwargs.update(dev_conf.get('params', {}))
            
            module_name, class_name = dev_conf['worker_class'].rsplit('.', 1)
            DeviceClass = getattr(importlib.import_module('devices.'+module_name), class_name)
            
            workers.append((name, DeviceClass, kwargs))
        except Exception as e:
            print("Loading device {} failed.".format(dev))
            traceback.print_exc(file=sys.stdout)

    return workers
