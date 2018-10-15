
import time
from src.measurement_file import MeasurementFile

file = MeasurementFile('test_file.h5')
N = 10
for i in range(N):
    trivista.start_accumulation()
    while not trivista.is_accumulation_finished():
        time.sleep(0.1)
    wavelengths,data = trivista.get_spectrum()
    file.save_snapshot(x=wavelengths, y=i, z=data)
    print("%d/%d" % (i,N))
file.close()
