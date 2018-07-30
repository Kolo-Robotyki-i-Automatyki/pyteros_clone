# -*- coding: utf-8 -*-

from enum import Enum
from numpy import nan

class Device:
    """ A prototype of a class representing a single device, 
    e.g. a positioner or a spectrometer """
    def __init__(self):
        self.priority = Device.Priority.Normal
        active_devices.append(self)
        
    class Priority(Enum):
        Critical = 1 # Experiment is stopped if device fails
        Semicritical = 2 # Experiment is stopped if a request fails
        Normal = 3 # Experiment is resumed when communication is restored
        Optional = 4 # Experiment continoues even if device fails
    
    def name(self):
        return type(self).__name__


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


""" A list of devices """
active_devices = []