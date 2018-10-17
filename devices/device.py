'''# -*- coding: utf-8 -*-

This code was originally written by Tomasz Kazimierczuk for LUMS - Laboratory
of Ultrafast MagnetoSpectroscopy at Faculty of Physics, University of Warsaw

'''
from enum import Enum
from numpy import nan
import configparser

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




def load_devices(use_gui=False, parent=None):
    config = configparser.ConfigParser()
    config.read('devices.ini')
    sections = [config[name] for name in config.sections()]
    for section in sections:
        try:
            if section['enabled'].lower() in ['true', '1', 't', 'y', 'yes']:
                section.enabled = True
            else:
                section.enabled = False
        except:
            section.enabled = True
           
    if use_gui:
        from PyQt5 import QtWidgets
        dialog = QtWidgets.QDialog(parent)
        dialog.setWindowTitle("Select devices")
        layout = QtWidgets.QVBoxLayout()
        dialog.setLayout(layout)
        for section in sections:
            checkbox = QtWidgets.QCheckBox(section.name)
            checkbox.setChecked(section.enabled)
            section.checkbox = checkbox
            layout.addWidget(checkbox)
        buttonbox = QtWidgets.QDialogButtonBox()
        buttonbox.addButton("Start", QtWidgets.QDialogButtonBox.AcceptRole)
        buttonbox.accepted.connect(dialog.accept)
        layout.addWidget(buttonbox)
        result = dialog.exec_()
        changed = False
        for section in sections:
            oldstate = section.enabled
            section.enabled = section.checkbox.isChecked()
            if oldstate ^ section.enabled:
                changed = True
            section['enabled'] = str(section.enabled).lower()
        if changed:
            with open('devices.ini', 'w') as configfile:
                config.write(configfile)
    
    for section in config.sections():
        try:
            items = dict(config.items(section))
            if 'enabled' in items:
                if items['enabled'].lower() in ['true', '1', 't', 'y', 'yes']:
                    del(items['enabled'])
                else:
                    continue
            module_name, class_name = items['class'].rsplit(".", 1)
            kwargs = items.copy()
            kwargs.pop('class')
            DeviceClass = getattr(importlib.import_module('devices.'+module_name), class_name)
            instance = DeviceClass(**kwargs)
            active_devices[section] = instance
        except Exception as e:
            print("Loading device %s failed." % section)
            traceback.print_exc(file=sys.stdout)


def load_workers():
    config = configparser.ConfigParser()
    config.read('local_devices.ini')
    workers = []
    for section in config.sections():
        try:
            items = dict(config.items(section))
            if 'enabled' in items:
                if items['enabled'].lower() in ['true', '1', 't', 'y', 'yes']:
                    del(items['enabled'])
                else:
                    continue
            module_name, class_name = items['class'].rsplit(".", 1)
            name = items['name']
            kwargs = items.copy()
            kwargs.pop('class')
            kwargs.pop('name')
            DeviceClass = getattr(importlib.import_module('devices.'+module_name), class_name)
            workers.append( (name, DeviceClass, kwargs) )
        except Exception as e:
            print("Loading device %s failed." % section)
            traceback.print_exc(file=sys.stdout)
    return workers
                        