import socket
import traceback
import threading
import time
import argparse

ANDROID_APP_PORT = 8192

class Orientation(object):
    def __init__(self, host, port, readout_id, debug_log=False):
        self._readout_id = readout_id

        self._s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._s.bind((host, port))

        self._last_readout = [0, 0, 0]

        self._debug_log = debug_log

        self._reading_thread = None
        self._is_running = False
        self.start()

    def _log(self, msg):
        if self._debug_log:
            print('[{}] {}'.format(time.time(), msg))

    def _collect_data(self):
        while self._is_running:
            try:
                message, address = self._s.recvfrom(ANDROID_APP_PORT)
                self._log(message)
                message = message.decode('ascii')
                values = message.split(',')
                values = values[1:] # ommit the timestamp

                while len(values) > 0:
                    if len(values) < 4:
                        log("Incomplete message: {}".format(values))
                        break

                    packet = values[0:4]
                    values = values[4:]
                    id = int(packet[0])
                    readout = [float(val.strip()) for val in packet[1:]]
                    self._log("{}: {}".format(id, readout))

                    if id == self._readout_id:
                        self._last_readout = readout

            except (KeyboardInterrupt, SystemExit):
                    raise
            except:
                traceback.print_exc()

    def start(self):
        if self._is_running:
            self._log("Already running")
            return

        self._log("Start reading measurements")

        self._is_running = True
        self._reading_thread = threading.Thread(target=self._collect_data)
        self._reading_thread.daemon = True
        self._reading_thread.start()

    def stop(self):
        if not self._is_running:
            self._log("Already stopped")

        self._log("Stop reading measurements")

        self._is_running = False
        self._reading_thread.join()

    def get_orientation(self):
        return self._last_readout


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('host', type=str)
    parser.add_argument('port', type=int)
    parser.add_argument('readout_id', type=int)
    args = parser.parse_args()

    receiver = Orientation(host=args.host, port=args.port, readout_id=args.readout_id, debug_log=True)

    readouts = []
    for i in range(0, 5):
        readouts.append(receiver.get_orientation())
        time.sleep(3)

    print('----------')
    print('Collected readouts:')
    for readout in readouts:
        print(readout)
    print('----------')

    receiver.stop()

