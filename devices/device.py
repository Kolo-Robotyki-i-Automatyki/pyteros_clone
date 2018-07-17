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
    
    

""" A list of devices """
active_devices = {}

import h5py
import numpy as np

class MeasurementFile:
    """ A class representing a measurement, i.e. a series of data.
        The data is a HDF5 file """
    def __init__(self, filename):
        self.file = h5py.File(filename, 'w')
        self.points = 0
    
    def close(self):
        self.file.close()
        
    def appendPoint(self):
        self.points += 1
        for dev in active_devices:
            group = self.file.require_group(dev.name)
            self._appendSubgroup(group, dev.status())
        self.file.flush()
        
    def _appendSubgroup(self, group, d):
        for key in d:
            val = d[key]
            key = str(key)
            
            if type(val) == dict:
                subgroup = group.require_group(key)
                self._appendSubgroup(subgroup, val)
            elif type(val) in (int, float):
                if key not in group:
                    group.create_dataset(key, shape=(self.points,), maxshape=(None,))
                ds = group[key]
                ds.resize( (self.points,) )
                ds[self.points-1] = val
            elif type(val) in (list, np.ndarray):
                if key not in group:
                    group.create_dataset(key, shape=(self.points,len(val)), maxshape=(None,len(val)))
                ds = group[key]
                ds.resize( (self.points, len(val)) )
                ds[self.points-1,:] = np.array(val)