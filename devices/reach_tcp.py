import socket
import threading
import time
import pynmea2

REACH_ROVER_HOST = "10.1.1.99"
REACH_ROVER_PORT = 9099
BUFSIZE = 2**16

class Reach():
    def __init__(self, host=REACH_ROVER_HOST, port=REACH_ROVER_PORT, debug_log=False):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))
        self.streamreader = pynmea2.NMEAStreamReader()

        self.status = {}
        self.tcp_lock = threading.Lock()
        self.tcp_thread = threading.Thread(target=self.loop_tcp)
        self.tcp_thread.start()

    def get_status(self):
        with self.tcp_lock:
            status = self.status
        return status


    def loop_tcp(self):
        while 1:
            data = self.socket.recv(BUFSIZE).decode("utf-8")
            for msg in self.streamreader.next(data):
                with self.tcp_lock:
                    try:
                        for i in range(len(msg.fields)):
                            self.status[msg.fields[i][0]] = msg.data[i]
                    except IndexError:
                        pass

#if __name__ == "__main__":
#reach = Reach()
#while True:
#    time.sleep(0.5)
#    with reach.tcp_lock:
#        print(reach.status)
