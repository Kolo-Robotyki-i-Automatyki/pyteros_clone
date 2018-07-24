# -*- coding: utf-8 -*-

from enum import Enum

class Device:
    """ Prototype for a class represinting a single device, 
    e.g. a positioner or a spectrometer """
    def __init__(self):
        self.priority = Device.Priority.Normal
        
    class Priority(Enum):
        Critical = 1 # Experiment is stopped if device fails
        Semicritical = 2 # Experiment is stopped if a request fails
        Normal = 3 # Experiment is resumed when communication is restored
        Optional = 4 # Experiment continoues even if device fails
    
    def name(self):
        return type(self).__name__


""" A list of devices """
active_devices = {}