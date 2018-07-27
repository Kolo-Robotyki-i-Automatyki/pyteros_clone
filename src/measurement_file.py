# -*- coding: utf-8 -*-

import h5py

class MeasurementFile:
    def __init__(self, filename, device_list):
        self.device_list = device_list
        self.n = 0
        self.f = h5py.File('mytestfile.hdf5', 'w')
    
    def close(self):
        self.f.close()
    
    def save_snapshot(self):
        data = {d.name(): d.status_to_save() for d in self.device_list}
        
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