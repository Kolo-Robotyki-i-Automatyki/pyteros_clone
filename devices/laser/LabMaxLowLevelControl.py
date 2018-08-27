# -*- coding: mbcs -*-
# Created by makepy.py version 0.5.01
# By python version 3.6.4 |Anaconda custom (32-bit)| (default, Jan 16 2018, 10:21:59) [MSC v.1900 32 bit (Intel)]
# From type library 'labmaxlowlevelcontrol.ocx'
# On Mon Aug 27 14:55:01 2018
'LabMaxLowLevelControl 1.0 Type Library'
makepy_version = '0.5.01'
python_version = 0x30604f0

import win32com.client.CLSIDToClass, pythoncom, pywintypes
import win32com.client.util
from pywintypes import IID
from win32com.client import Dispatch

# The following 3 lines may need tweaking for the particular server
# Candidates are pythoncom.Missing, .Empty and .ArgNotFound
defaultNamedOptArg=pythoncom.Empty
defaultNamedNotOptArg=pythoncom.Empty
defaultUnnamedArg=pythoncom.Empty

CLSID = IID('{5F331069-3778-4225-8DE7-DC3A7D090EF9}')
MajorVersion = 1
MinorVersion = 0
LibraryFlags = 8
LCID = 0x0

class constants:
	COM_MODE_GPIB                 =2          # from enum LabMaxCommunicationMode
	COM_MODE_NONE                 =0          # from enum LabMaxCommunicationMode
	COM_MODE_RS232                =3          # from enum LabMaxCommunicationMode
	COM_MODE_USB                  =1          # from enum LabMaxCommunicationMode

from win32com.client import DispatchBaseClass
class ILabMaxLowLevCtl(DispatchBaseClass):
	'ILabMaxLowLevCtl Interface'
	CLSID = IID('{1212BA48-F43B-4640-8122-FBCB52F18CBD}')
	coclass_clsid = IID('{D5D146E2-4398-415B-9773-B48F6620D2B5}')

	def ConnectToMeter(self, iMeterIndex=defaultNamedNotOptArg):
		'method ConnectToMeter'
		return self._oleobj_.InvokeTypes(3, LCID, 1, (2, 0), ((2, 1),),iMeterIndex
			)

	def DeInitialize(self):
		'method DeInitialize'
		return self._oleobj_.InvokeTypes(9, LCID, 1, (2, 0), (),)

	def DisconnectFromMeter(self, iMeterIndex=defaultNamedNotOptArg):
		'method DisconnectFromMeter'
		return self._oleobj_.InvokeTypes(4, LCID, 1, (2, 0), ((2, 1),),iMeterIndex
			)

	def GetNextString(self, iMeterIndex=defaultNamedNotOptArg):
		'method GetNextString'
		# Result is a Unicode object
		return self._oleobj_.InvokeTypes(2, LCID, 1, (8, 0), ((2, 1),),iMeterIndex
			)

	def Initialize(self):
		'method Initialize'
		return self._oleobj_.InvokeTypes(8, LCID, 1, (2, 0), (),)

	# The method RS232Settings is actually a property, but must be used as a method to correctly pass the arguments
	def RS232Settings(self, iMeterIndex=defaultNamedNotOptArg):
		'property RS232Settings'
		# Result is a Unicode object
		return self._oleobj_.InvokeTypes(6, LCID, 2, (8, 0), ((2, 1),),iMeterIndex
			)

	def SendCommandOrQuery(self, iMeterIndex=defaultNamedNotOptArg, iCommandOrQuery=defaultNamedNotOptArg):
		'method SendCommandOrQuery'
		return self._oleobj_.InvokeTypes(1, LCID, 1, (2, 0), ((2, 1), (8, 1)),iMeterIndex
			, iCommandOrQuery)

	# The method SerialNumber is actually a property, but must be used as a method to correctly pass the arguments
	def SerialNumber(self, iMeterIndex=defaultNamedNotOptArg):
		'property SerialNumber'
		# Result is a Unicode object
		return self._oleobj_.InvokeTypes(7, LCID, 2, (8, 0), ((2, 1),),iMeterIndex
			)

	# The method SetRS232Settings is actually a property, but must be used as a method to correctly pass the arguments
	def SetRS232Settings(self, iMeterIndex=defaultNamedNotOptArg, arg1=defaultUnnamedArg):
		'property RS232Settings'
		return self._oleobj_.InvokeTypes(6, LCID, 4, (24, 0), ((2, 1), (8, 1)),iMeterIndex
			, arg1)

	_prop_map_get_ = {
		"CommunicationMode": (5, 2, (3, 0), (), "CommunicationMode", None),
		"GPIBSettings": (10, 2, (8, 0), (), "GPIBSettings", None),
	}
	_prop_map_put_ = {
		"CommunicationMode": ((5, LCID, 4, 0),()),
		"GPIBSettings": ((10, LCID, 4, 0),()),
	}
	def __iter__(self):
		"Return a Python iterator for this object"
		try:
			ob = self._oleobj_.InvokeTypes(-4,LCID,3,(13, 10),())
		except pythoncom.error:
			raise TypeError("This object does not support enumeration")
		return win32com.client.util.Iterator(ob, None)

class _ILabMaxLowLevCtlEvents:
	'_ILabMaxLowLevCtlEvents Interface'
	CLSID = CLSID_Sink = IID('{4408BF92-B376-4788-B880-2B4DE2C63F38}')
	coclass_clsid = IID('{D5D146E2-4398-415B-9773-B48F6620D2B5}')
	_public_methods_ = [] # For COM Server support
	_dispid_to_func_ = {
		        1 : "OnMeterAdded",
		        2 : "OnMeterRemoved",
		        3 : "OnAsynchronousNotification",
		        4 : "OnUSBStreamingPacket",
		}

	def __init__(self, oobj = None):
		if oobj is None:
			self._olecp = None
		else:
			import win32com.server.util
			from win32com.server.policy import EventHandlerPolicy
			cpc=oobj._oleobj_.QueryInterface(pythoncom.IID_IConnectionPointContainer)
			cp=cpc.FindConnectionPoint(self.CLSID_Sink)
			cookie=cp.Advise(win32com.server.util.wrap(self, usePolicy=EventHandlerPolicy))
			self._olecp,self._olecp_cookie = cp,cookie
	def __del__(self):
		try:
			self.close()
		except pythoncom.com_error:
			pass
	def close(self):
		if self._olecp is not None:
			cp,cookie,self._olecp,self._olecp_cookie = self._olecp,self._olecp_cookie,None,None
			cp.Unadvise(cookie)
	def _query_interface_(self, iid):
		import win32com.server.util
		if iid==self.CLSID_Sink: return win32com.server.util.wrap(self)

	# Event Handlers
	# If you create handlers, they should have the following prototypes:
#	def OnMeterAdded(self, iMeterIndex=defaultNamedNotOptArg):
#		'method MeterAdded'
#	def OnMeterRemoved(self, iMeterIndex=defaultNamedNotOptArg):
#		'method MeterRemoved'
#	def OnAsynchronousNotification(self, iMeterIndex=defaultNamedNotOptArg):
#		'method AsynchronousNotification'
#	def OnUSBStreamingPacket(self, iMeterIndex=defaultNamedNotOptArg, iStreamingPacket=defaultNamedNotOptArg):
#		'method USBStreamingPacket'


from win32com.client import CoClassBaseClass
# This CoClass is known by the name 'LabMaxLowLevelControl.LabMaxLowLevCtl.1'
class CLabMaxLowLevCtl(CoClassBaseClass): # A CoClass
	# LabMaxLowLevCtl Class
	CLSID = IID('{D5D146E2-4398-415B-9773-B48F6620D2B5}')
	coclass_sources = [
		_ILabMaxLowLevCtlEvents,
	]
	default_source = _ILabMaxLowLevCtlEvents
	coclass_interfaces = [
		ILabMaxLowLevCtl,
	]
	default_interface = ILabMaxLowLevCtl

ILabMaxLowLevCtl_vtables_dispatch_ = 1
ILabMaxLowLevCtl_vtables_ = [
	(( 'SendCommandOrQuery' , 'iMeterIndex' , 'iCommandOrQuery' , 'oResult' , ), 1, (1, (), [ 
			 (2, 1, None, None) , (8, 1, None, None) , (16386, 10, None, None) , ], 1 , 1 , 4 , 0 , 28 , (3, 0, None, None) , 0 , )),
	(( 'GetNextString' , 'iMeterIndex' , 'oString' , ), 2, (2, (), [ (2, 1, None, None) , 
			 (16392, 10, None, None) , ], 1 , 1 , 4 , 0 , 32 , (3, 0, None, None) , 0 , )),
	(( 'ConnectToMeter' , 'iMeterIndex' , 'oResult' , ), 3, (3, (), [ (2, 1, None, None) , 
			 (16386, 10, None, None) , ], 1 , 1 , 4 , 0 , 36 , (3, 0, None, None) , 0 , )),
	(( 'DisconnectFromMeter' , 'iMeterIndex' , 'oResult' , ), 4, (4, (), [ (2, 1, None, None) , 
			 (16386, 10, None, None) , ], 1 , 1 , 4 , 0 , 40 , (3, 0, None, None) , 0 , )),
	(( 'CommunicationMode' , 'oCommunicationMode' , ), 5, (5, (), [ (16387, 10, None, None) , ], 1 , 2 , 4 , 0 , 44 , (3, 0, None, None) , 0 , )),
	(( 'CommunicationMode' , 'oCommunicationMode' , ), 5, (5, (), [ (3, 1, None, None) , ], 1 , 4 , 4 , 0 , 48 , (3, 0, None, None) , 0 , )),
	(( 'RS232Settings' , 'iMeterIndex' , 'oRS232Settings' , ), 6, (6, (), [ (2, 1, None, None) , 
			 (16392, 10, None, None) , ], 1 , 2 , 4 , 0 , 52 , (3, 0, None, None) , 0 , )),
	(( 'RS232Settings' , 'iMeterIndex' , 'oRS232Settings' , ), 6, (6, (), [ (2, 1, None, None) , 
			 (8, 1, None, None) , ], 1 , 4 , 4 , 0 , 56 , (3, 0, None, None) , 0 , )),
	(( 'SerialNumber' , 'iMeterIndex' , 'oSerialNumber' , ), 7, (7, (), [ (2, 1, None, None) , 
			 (16392, 10, None, None) , ], 1 , 2 , 4 , 0 , 60 , (3, 0, None, None) , 0 , )),
	(( 'Initialize' , 'oResult' , ), 8, (8, (), [ (16386, 10, None, None) , ], 1 , 1 , 4 , 0 , 64 , (3, 0, None, None) , 0 , )),
	(( 'DeInitialize' , 'oResult' , ), 9, (9, (), [ (16386, 10, None, None) , ], 1 , 1 , 4 , 0 , 68 , (3, 0, None, None) , 0 , )),
	(( 'GPIBSettings' , 'oGPIBSettings' , ), 10, (10, (), [ (16392, 10, None, None) , ], 1 , 2 , 4 , 0 , 72 , (3, 0, None, None) , 0 , )),
	(( 'GPIBSettings' , 'oGPIBSettings' , ), 10, (10, (), [ (8, 1, None, None) , ], 1 , 4 , 4 , 0 , 76 , (3, 0, None, None) , 0 , )),
]

RecordMap = {
}

CLSIDToClassMap = {
	'{4408BF92-B376-4788-B880-2B4DE2C63F38}' : _ILabMaxLowLevCtlEvents,
	'{1212BA48-F43B-4640-8122-FBCB52F18CBD}' : ILabMaxLowLevCtl,
	'{D5D146E2-4398-415B-9773-B48F6620D2B5}' : CLabMaxLowLevCtl,
}
CLSIDToPackageMap = {}
win32com.client.CLSIDToClass.RegisterCLSIDsFromDict( CLSIDToClassMap )
VTablesToPackageMap = {}
VTablesToClassMap = {
	'{1212BA48-F43B-4640-8122-FBCB52F18CBD}' : 'ILabMaxLowLevCtl',
}


NamesToIIDMap = {
	'_ILabMaxLowLevCtlEvents' : '{4408BF92-B376-4788-B880-2B4DE2C63F38}',
	'ILabMaxLowLevCtl' : '{1212BA48-F43B-4640-8122-FBCB52F18CBD}',
}

win32com.client.constants.__dicts__.append(constants.__dict__)

