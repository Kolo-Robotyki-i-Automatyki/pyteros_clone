# -*- coding: utf-8 -*-

import h5py
import devices
from numpy import ndarray,array

class MeasurementFile:
    def __init__(self, filename, x_data=None, y_data=None, z_data=None):
        """{x,y,z}_data indicates how the data is optional indication of the 
        *main* data. There are two possibilities:
            - it can be a function which will be called at each data point
            - it can be a list of strings to specify a data obtained anyway 
            by querying devices for status, e.g., ['apt','apt_60242834','position']
            """
        self.n = 0
        self.file = h5py.File(filename, 'w')
        
        self.main_data = {}
        for axis,source in (('x',x_data), ('y',y_data), ('z',z_data)):
            if not source:
                continue
            if callable(source):
                self.main_data[axis] = source
            else:
                try:
                    path = '/data_full/' + '/'.join(source)
                    self.file[axis] = h5py.SoftLink(path)
                except:
                    print("Error - data link not recognized in MeasurementFile class ")        
    
    def __del__(self):
        self.close()
    
    def close(self):
        self.file.close()
        
    def save_snapshot(self, **user_data):
        self.n += 1
        for key,func in self.main_data.items():
            self._save_data(self.file, key, func())
        
        for key,data in user_data.items():
            self._save_data(self.file, key, data)
        
        group = self.file.require_group('data_full')
        for name,device in devices.active_devices.items():
            try:
                self._save_subgroup(group, name, device.status())
            except:
                print("Error saving device %s" % name)
        self.file.flush()
        
    def _save_subgroup(self, parent, name, data):
        """ parent - the parent subgroup of HDF file
            name - id (string) of the current group
            data - dictionary of the data with string as keys"""
        group = parent.require_group(name)
        for key,value in data.items():
            self._save_data(group, key, value)
                
    def _save_data(self, group, name, value):
        if type(value) == dict:
            self._save_subgroup(group, name, value)
        elif type(value) in (int, float, bool, ndarray):
            value = array(value)
            newshape = (self.n,) + value.shape
            if name not in group:
                dset = group.create_dataset(name, shape=newshape, maxshape=(None,), dtype=value.dtype)
            else:
                dset = group[name]
                dset.resize( newshape )
            dset[-1] = value