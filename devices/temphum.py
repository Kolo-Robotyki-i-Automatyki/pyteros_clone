
import threading
import time
try:
    import Adafruit_DHT
except Exception:
    pass

class DHT22():
    def __init__(self, debug_log=False):
        self.air_humidity = 0
        self.air_temperature = 0
        self.lock_dht22 = threading.Lock()
        self.thread_dht22 = threading.Thread(target=self.loop_dht22)
        self.thread_dht22.start()

    def get_air_temperature(self):
        with self.lock_dht22:
            print([self.air_temperature, self.air_humidity])
            return round(self.air_temperature, 2)

    def get_air_humidity(self):
        with self.lock_dht22:
            return round(self.air_humidity, 2)

    def loop_dht22(self):
        while 1:
            try:
                time.sleep(0.1)
                hum, temp = Adafruit_DHT.read(Adafruit_DHT.DHT22, 4)
                print([hum,temp])
                if hum is not None and temp is not None:
                    with self.lock_dht22:
                        self.air_humidity = hum
                        self.air_temperature = temp
            except Exception as e:
                print(e)

if __name__ == "__main__":
    dht = DHT22()
    while True:
        time.sleep(0.5)
        print([dht.get_air_temperature(), dht.humidity()])
