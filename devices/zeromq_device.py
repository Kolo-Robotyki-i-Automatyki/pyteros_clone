# -*- coding: utf-8 -*-

from PyQt5 import QtCore
import zmq
import json
from . import device
import numpy as np
import base64

delegated_methods_db = {}
def handler(cls,name):
    def decorator(fn):
        delegated_methods_db[(cls,name)] = fn
        return fn
    return decorator

context = zmq.Context()



class ArrayEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return {"dtype": obj.dtype.str,
                    "shape": obj.shape,
                    "data": base64.b64encode(obj.tostring()).decode('ascii')}
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)

def array_object_hook(d):
    try:
        a = np.frombuffer(base64.standard_b64decode(d["data"]),
                          dtype=d["dtype"])
        a.reshape(d["shape"])
        return a
    except:
        return d


class DeviceOverZeroMQ(device.Device):
    def __init__(self, req_port, pub_port=None, host="localhost"):           
        self.thread = {}
        self.channel = "tcp://"+host+":"+str(req_port)
        self.client = context.socket(zmq.REQ)
        self.client.connect(self.channel)
        self.poll = zmq.Poller()
        self.poll.register(self.client, zmq.POLLIN)
        self.request_timeout = 2000 # 2s in milliseconds
        if pub_port:
            self.pub_channel = "tcp://"+host+":"+str(pub_port)
        else:
            self.pub_channel = None
        self.createDelegatedMethods("DeviceWorker")
        
        

    def _makeFun(self, cls_name, method_name):
        def fun(self, *args):
            #print("internal: func: " + str(method_name))
            obj = (method_name, cls_name, args)
            msg = json.dumps(obj, cls=ArrayEncoder).encode('ascii')
            self.client.send(msg)
            
            
            socks = dict(self.poll.poll(self.request_timeout))
            if socks.get(self.client) == zmq.POLLIN:
                return self.client.recv_json(object_hook=array_object_hook)
            else:
                # Timeout. 
                # Socket is confused. Close and reopen to reset its state.
                self.client.setsockopt(zmq.LINGER, 0)
                self.client.close()
                self.poll.unregister(self.client)
                self.client = context.socket(zmq.REQ)
                self.client.connect(self.channel)
                self.poll.register(self.client, zmq.POLLIN)
                raise ConnectionError
                
        return fun
        

    def createDelegatedMethods(self, name):
        for (cls, method_name) in delegated_methods_db:
            if cls == name:
                setattr(self.__class__, method_name, self._makeFun(cls,method_name))
    
    class ZeroMQ_Listener(QtCore.QObject):
        message = QtCore.pyqtSignal(object)
        
        def __init__(self,channel, topic):
            QtCore.QObject.__init__(self)
            
            self.socket = context.socket(zmq.SUB)
            print(channel)
            self.socket.connect (channel)
            self.socket.setsockopt(zmq.SUBSCRIBE, topic)
             
            self.running = True
         
        def loop(self):
            while self.running:
                msg = self.socket.recv_multipart()[1].decode('ascii')
                status = json.loads(msg, object_hook=array_object_hook)
                self.message.emit(status)
            
    def createListenerThread(self, updateSlot, topic=b'status'):
        if not self.pub_channel:
            print("Error: no PUB port given")
            return
        if topic not in self.thread:
            thread = QtCore.QThread()
            zeromq_listener = DeviceOverZeroMQ.ZeroMQ_Listener(self.pub_channel, topic)
            zeromq_listener.moveToThread(thread)
            thread.started.connect(zeromq_listener.loop)
            QtCore.QTimer.singleShot(0, thread.start)
            self.thread[topic] = (thread, zeromq_listener)
        self.thread[topic][1].message.connect(updateSlot)
        
        
from multiprocessing import Process


from random import randint
   
import time
import threading

def reminderFunc(context,req_channel,rate=0.1):
    reminder = context.socket(zmq.REQ)
    reminder.connect(req_channel)
    try:
        while True:
            reminder.send_json( ("status", None, None))
            reminder.recv_json()
            time.sleep(rate)
    except:
        reminder.close()
        raise




class Logger():
    def __init__(self, socket, mutex, stream="out"):
        self.socket = socket
        self.envelope = stream.encode('ascii')
        self.mutex_for_pubchannel = mutex

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.mutex_for_pubchannel.lock()
            self.socket.send_multipart([self.envelope, line.rstrip().encode('ascii')])
            self.mutex_for_pubchannel.unlock()

    def flush(self):
        pass


class DeviceWorker(Process):
    def __init__(self, req_port, pub_port, refresh_rate=0.2):
        self.REQchannel = "tcp://*:" + str(req_port)
        self.PUBchannel = "tcp://*:" + str(pub_port)
        self.rep_channel = "tcp://localhost:"+str(req_port)
        self.refresh_rate = refresh_rate
        super().__init__()

    @handler("DeviceWorker", "status")
    def status(self):
        return {}

    def init_device(self):
        pass

    def send_via_pubchannel(self, topic, obj):
        msg = json.dumps(obj, cls=ArrayEncoder).encode('ascii')
        self.mutex_for_pubchannel.lock()
        self.notifier.send_multipart([topic, msg])
        self.mutex_for_pubchannel.unlock()

    def run(self):
        print("starting process")
        self.mutex_for_pubchannel = QtCore.QMutex()
        context = zmq.Context(1)
        server = context.socket(zmq.REP)
        server.bind(self.REQchannel)
        
        self.notifier = context.socket(zmq.PUB)
        self.notifier.bind(self.PUBchannel)
        
        import sys
        sys.stdout = Logger(self.notifier, self.mutex_for_pubchannel, "stdout")
        sys.stderr = Logger(self.notifier, self.mutex_for_pubchannel, "stderr")
        time.sleep(0.5)
        
        reminderThread = threading.Thread(target=reminderFunc,
                                          args=(context,self.rep_channel,self.refresh_rate))
        reminderThread.start()
        
        self.init_device()

        while True:
            request = server.recv_json()
            if request[0] == 'quit':
                break
            if request[0] == "status":
                msg = json.dumps(self.status(), cls=ArrayEncoder).encode('ascii')
                server.send(msg)
                self.mutex_for_pubchannel.lock()
                self.notifier.send_multipart([b"status", msg])
                self.mutex_for_pubchannel.unlock()
                continue
            
            try:
                f = delegated_methods_db[(request[1],request[0])]
                args = request[2]
                msg = json.dumps(f(self,*args), cls=ArrayEncoder).encode('ascii')
                server.send(msg)
            except Exception as e:
                print("Exception: ", str(e))
                server.send_json("ERROR processing request")
        reminderThread.join()
                
        print("quitting process")
        server.close()
        reminderThread.join()
        context.term()
        print("finally the whole process quits")
    