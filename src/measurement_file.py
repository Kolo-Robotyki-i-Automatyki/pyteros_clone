# -*- coding: utf-8 -*-

import h5py
import devices
from numpy import ndarray,array
import numpy as np

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
        self.filename = filename
        
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
    
    def save_txt(self):
        """ Try to write ASCII file with the main data """
        print("Attempting to export txt file")
        if 'z' not in self.file:
            print("No Z data in the file")
            return
        z = array(self.file['z'])
        if len(z.shape) != 2:
            print("Z data is not 2D array")
            return
        
        offset=0
        if 'x' in self.file:
            x = array(self.file['x'])[0]
            if len(x.shape)!=1 or len(x) != z.shape[1]:
                print("Mismatch between the size of x (%d) and z (%d)" %(len(x), z.shape[1]))
                return
            z = np.concatenate((x[np.newaxis,:],z),axis=0)
            offset=1
        
        if 'y' in self.file:
            y = array(self.file['y'])
            if len(y.shape)!=1 or len(y) != z.shape[0]-offset:
                print("Mismatch between the size of y (%d) and z (%d)" %(len(x), z.shape[0]-offset))
                return
            if offset:
                y = np.r_[0,y]
            z = np.concatenate((y[:,np.newaxis],z),axis=1)
        
        np.savetxt(self.filename+'.txt',z)
        
    
    def close(self):
        self.save_txt()
        self.file.close()
        
    def save_snapshot(self, **user_data):
        """ We save the state of all active devices """
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
        if type(value) == list:
            try:
                value=array(value)
            except:
                pass
        #now we start actual saving:
        if type(value) == dict:
            self._save_subgroup(group, name, value)
        elif type(value) in (int, float, bool, np.float, np.float16, np.float32, 
                             np.float64, np.int, np.int8, np.int16, np.int32, 
                             np.int64, np.uint, np.uint8, np.uint16, np.uint32, 
                             np.uint64, np.ndarray):
            value = array(value)
            newshape = (self.n,) + value.shape
            if name not in group:
                dset = group.create_dataset(name, shape=newshape, maxshape=(None,)+value.shape, dtype=value.dtype)
            else:
                dset = group[name]
                dset.resize( newshape )
            dset[-1] = value
