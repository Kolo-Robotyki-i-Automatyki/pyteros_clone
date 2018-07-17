# -*- coding: utf-8 -*-

from PyQt5 import QtCore
import zmq
import json
from . import device

delegated_methods_db = {}
def handler(cls,name):
    def decorator(fn):
        delegated_methods_db[(cls,name)] = fn
        return fn
    return decorator

context = zmq.Context()

class DeviceOverZeroMQ:
    def __init__(self, req_port, pub_port=None, host="localhost"):
        self.channel = "tcp://"+host+":"+str(req_port)
        self.client = context.socket(zmq.REQ)
        self.client.connect(self.channel)
        if pub_port:
            self.pub_channel = "tcp://"+host+":"+str(pub_port)
        else:
            self.pub_channel = None

    def _makeFun(self, cls_name, method_name):
        def fun(self, *args):
            #print("internal: func: " + str(method_name))
            obj = (method_name, cls_name, args)
            self.client.send_json(obj)
            return self.client.recv_json()
        return fun
        

    def createDelegatedMethods(self, name):
        for (cls, method_name) in delegated_methods_db:
            if cls == name:
                setattr(self.__class__, method_name, self._makeFun(cls,method_name))
    
    class ZeroMQ_Listener(QtCore.QObject):
        message = QtCore.pyqtSignal(object)
        
        def __init__(self,channel):
            QtCore.QObject.__init__(self)
            
            self.socket = context.socket(zmq.SUB)
            print(channel)
            self.socket.connect (channel)
            self.socket.setsockopt(zmq.SUBSCRIBE, b'status')
             
            self.running = True
         
        def loop(self):
            while self.running:
                msg = self.socket.recv_multipart()[1].decode('ascii')
                status = json.loads(msg)
                self.message.emit(status)
            
    def createListenerThread(self, updateSlot):
        if not self.pub_channel:
            print("Error: no PUB port given")
            return
        self.thread = QtCore.QThread()
        self.zeromq_listener = DeviceOverZeroMQ.ZeroMQ_Listener(self.pub_channel)
        self.zeromq_listener.moveToThread(self.thread)
        self.thread.started.connect(self.zeromq_listener.loop)
        self.zeromq_listener.message.connect(updateSlot)
        QtCore.QTimer.singleShot(0, self.thread.start)
        
        
        
from multiprocessing import Process


from random import randint
   
import time
import threading

def reminderFunc(context,req_channel,rate=0.1):
    print("Starting thread")
    reminder = context.socket(zmq.REQ)
    reminder.connect(req_channel)
    try:
        while True:
            reminder.send_json( ("status?", None, None))
            reminder.recv_json()
            time.sleep(rate)
    except:
        reminder.close()
        raise
    print("Thread finishing")




class Logger():
    def __init__(self, socket, stream="out"):
        self.socket = socket
        self.envelope = stream.encode('ascii')

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.socket.send_multipart([self.envelope, line.rstrip().encode('ascii')])

    def flush(self):
        pass


class DeviceWorker(Process):
    def __init__(self, req_port, pub_port, refresh_rate=0.2):
        self.REQchannel = "tcp://*:" + str(req_port)
        self.PUBchannel = "tcp://*:" + str(pub_port)
        self.rep_channel = "tcp://localhost:"+str(req_port)
        self.refresh_rate = refresh_rate
        super().__init__()

    def status(self):
        return {}
    

    def init_device(self):
        pass

    def run(self):
        print("starting process")
        context = zmq.Context(1)
        server = context.socket(zmq.REP)
        server.bind(self.REQchannel)
        
        notifier = context.socket(zmq.PUB)
        notifier.bind(self.PUBchannel)
        
        import sys
        sys.stdout = Logger(notifier, "stdout")
        sys.stderr = Logger(notifier, "stderr")
        time.sleep(0.5)
        
        reminderThread = threading.Thread(target=reminderFunc,
                                          args=(context,self.rep_channel,self.refresh_rate))
        reminderThread.start()
        
        self.init_device()

        while True:
            request = server.recv_json()
            if request[0] == 'quit':
                break
            if request[0] == "status?":
                msg = json.dumps(self.status()).encode('ascii')
                server.send(msg)
                notifier.send_multipart([b"status", msg])
                continue
            
            print("Raw request:", request)
            print(request)
            try:
                f = delegated_methods_db[(request[1],request[0])]
                args = request[2]
                server.send_json(f(self,*args))
            except Exception as e:
                print("Exception: ", str(e))
                server.send_json("ERROR processing request")
        reminderThread.join()
                
        print("quitting process")
        server.close()
        reminderThread.join()
        context.term()
        print("finally the whole process quits")
    