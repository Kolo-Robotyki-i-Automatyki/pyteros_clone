
from devices.zeromq_device import DeviceWorker,DeviceOverZeroMQ,remote,include_remote_methods
from PyQt5 import QtWidgets,QtCore,QtGui
from time import perf_counter as clock
from time import sleep, time
from collections import deque
from devices.pid import PID
#from devices.temphum import DHT22
from devices.ik import axes_to_arm, axes_to_rover, arm_to_axes, arm_to_rover, rover_to_arm, rover_to_axes
from devices.autonomy import Autonomy
from scipy import optimize
import subprocess
import math
from math import sin, cos
import threading
try:
    import serial
except Exception:
    pass

from devices.reach_tcp import Reach

try:
    import can
except Exception:
    pass

try:
    import Adafruit_DHT
except Exception:
    pass

try:
    from devices.markers_reader import TagReader
except Exception:
    pass

    print("ModuleNotFoundError: No module named 'can'")
PI = 3.14159265357
default_req_port = 10200
default_pub_port = 10201

erpm_per_meter = 600 / 1.568 # 96/R_wheel
L1 = 602.
L2 = 478.
deg = PI / 180

arm_lower = 190
arm_upper = 191
arm_rot = 200
grip_lat = 201
relative_position_default_origin = (52.211415, 20.983336)

def list_to_int(bytes):
    return int.from_bytes(bytearray(bytes), byteorder='big', signed=True)

lipo_characteristics = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,6,6,6,6,6,6,6,6,6,7,7,7,7,8,8,8,8,8,9,9,9,10,10,10,11,11,12,12,12,13,13,13,14,14,14,15,16,16,17,17,18,19,19,20,20,21,22,22,24,25,26,27,28,29,31,33,34,36,37,39,41,43,45,46,47,49,50,52,53,54,55,56,56,57,58,59,59,60,62,63,64,64,65,66,66,67,68,68,69,69,70,71,71,72,72,73,73,74,74,75,75,76,77,77,78,78,79,79,80,80,81,81,82,82,83,83,84,84,85,85,86,86,87,87,87,88,88,89,89,90,90,90,91,91,92,92,92,93,93,94,94,94,95,95,95,96,96,96,97,97,97,97,98,98,98,99,99,99,99,99,99,99,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100]
slopepoints = [(15.45, 28.35, 4.67246), (16.45, 28.35, 4.37456), (17.45, 28.35, 4.31296), (18.45, 28.35, 4.39868), (19.45, 28.35, 4.28906), (20.45, 28.35, 4.32717), (21.45, 28.35, 4.37586), (22.45, 28.35, 4.38928), (23.45, 28.35, 4.63847), (24.45, 28.35, 4.80709), (25.45, 28.35, 4.94574), (26.45, 28.35, 4.87193), (27.45, 28.35, 4.89811), (28.45, 28.35, 4.83461), (29.45, 28.35, 4.6375), (30.45, 28.35, 4.309), (31.45, 28.35, 3.12805), (35.45, 28.35, 2.6068), (36.45, 28.35, 2.74263), (37.45, 28.35, 2.91152), (38.45, 28.35, 3.1996), (39.45, 28.35, 3.25149), (40.45, 28.35, 3.5623), (41.45, 28.35, 3.35973), (42.45, 28.35, 3.3138), (43.45, 28.35, 3.29648), (44.45, 28.35, 3.32524), (45.45, 28.35, 3.46167), (46.45, 28.35, 3.60157), (47.45, 28.35, 3.79355), (48.45, 28.35, 4.02201), (49.45, 28.35, 4.52731), (50.45, 28.35, 4.86947), (51.45, 28.35, 4.8223), (12.45, 27.35, 4.83795), (13.45, 27.35, 3.9234), (14.45, 27.35, 3.04665), (15.45, 27.35, 3.27196), (16.45, 27.35, 3.25679), (17.45, 27.35, 3.4583), (46.45, 27.35, 1.96646), (47.45, 27.35, 1.03066), (51.45, 27.35, 3.54027), (52.45, 27.35, 3.77183), (9.45, 26.35, 4.92238), (10.45, 26.35, 5.3372), (11.45, 26.35, 4.29051), (12.45, 26.35, 2.71949), (13.45, 26.35, 2.61592), (14.45, 26.35, 4.41315), (15.45, 26.35, 3.59222), (46.45, 26.35, 3.99773), (47.45, 26.35, 1.84517), (48.45, 26.35, 1.73388), (49.45, 26.35, 1.7996), (50.45, 26.35, 3.62606), (52.45, 26.35, 3.3602), (8.45, 25.35, 5.28004), (9.45, 25.35, 5.20129), (10.45, 25.35, 3.11821), (11.45, 25.35, 2.53435), (12.45, 25.35, 2.99521), (13.45, 25.35, 4.9829), (18.45, 25.35, 3.78438), (19.45, 25.35, 3.97856), (52.45, 25.35, 3.09939), (7.45, 24.35, 5.06317), (8.45, 24.35, 5.1336), (10.45, 24.35, 1.93102), (11.45, 24.35, 2.7663), (12.45, 24.35, 5.36272), (18.45, 24.35, 3.33588), (19.45, 24.35, 3.55329), (20.45, 24.35, 3.82842), (21.45, 24.35, 4.02612), (32.45, 24.35, 2.42955), (33.45, 24.35, 4.04781), (52.45, 24.35, 2.77262), (6.45, 23.35, 4.87077), (7.45, 23.35, 5.09875), (10.45, 23.35, 2.31587), (11.45, 23.35, 3.1558), (17.45, 23.35, 2.73352), (18.45, 23.35, 2.75498), (19.45, 23.35, 3.82536), (20.45, 23.35, 4.18246), (21.45, 23.35, 4.27154), (22.45, 23.35, 3.65882), (23.45, 23.35, 3.72874), (32.45, 23.35, 2.62824), (33.45, 23.35, 4.29342), (52.45, 23.35, 2.78319), (6.45, 22.35, 5.09298), (7.45, 22.35, 4.59447), (11.45, 22.35, 2.94304), (16.45, 22.35, 2.10661), (17.45, 22.35, 1.66258), (19.45, 22.35, 4.94735), (20.45, 22.35, 4.88982), (21.45, 22.35, 3.71379), (22.45, 22.35, 3.27853), (23.45, 22.35, 3.58563), (24.45, 22.35, 3.63597), (25.45, 22.35, 3.30702), (30.45, 22.35, 2.84462), (31.45, 22.35, 2.99582), (32.45, 22.35, 3.56419), (34.45, 22.35, 4.34723), (52.45, 22.35, 2.46076), (5.45, 21.35, 4.95189), (6.45, 21.35, 4.80978), (17.45, 21.35, 1.14379), (19.45, 21.35, 5.04999), (20.45, 21.35, 3.76865), (21.45, 21.35, 3.16754), (22.45, 21.35, 3.13121), (23.45, 21.35, 3.35848), (24.45, 21.35, 3.60229), (25.45, 21.35, 3.54438), (26.45, 21.35, 3.31328), (27.45, 21.35, 3.04019), (28.45, 21.35, 2.76078), (29.45, 21.35, 2.83783), (30.45, 21.35, 2.34379), (32.45, 21.35, 4.1968), (33.45, 21.35, 4.16241), (34.45, 21.35, 4.22503), (48.45, 21.35, 1.95143), (4.45, 20.35, 4.80286), (5.45, 20.35, 4.62655), (6.45, 20.35, 4.61206), (19.45, 20.35, 3.84068), (20.45, 20.35, 3.07742), (21.45, 20.35, 3.03095), (22.45, 20.35, 3.04193), (23.45, 20.35, 3.15688), (24.45, 20.35, 3.54497), (25.45, 20.35, 3.41385), (26.45, 20.35, 3.27165), (27.45, 20.35, 3.23149), (28.45, 20.35, 3.19344), (29.45, 20.35, 3.07924), (30.45, 20.35, 2.9401), (34.45, 20.35, 4.44364), (48.45, 20.35, 1.92873), (49.45, 20.35, 2.51191), (4.45, 19.35, 4.79926), (5.45, 19.35, 4.7683), (6.45, 19.35, 4.63947), (7.45, 19.35, 4.90791), (21.45, 19.35, 2.80909), (22.45, 19.35, 2.88003), (23.45, 19.35, 2.98542), (24.45, 19.35, 3.21593), (25.45, 19.35, 3.25124), (26.45, 19.35, 3.31128), (27.45, 19.35, 3.33312), (28.45, 19.35, 3.3278), (29.45, 19.35, 3.34281), (30.45, 19.35, 3.81105), (31.45, 19.35, 4.21824), (34.45, 19.35, 4.42831), (35.45, 19.35, 3.94319), (4.45, 18.35, 4.79037), (5.45, 18.35, 4.67323), (6.45, 18.35, 4.69853), (7.45, 18.35, 4.67695), (14.45, 18.35, 2.42996), (15.45, 18.35, 2.57635), (16.45, 18.35, 2.63056), (18.45, 18.35, 2.9962), (24.45, 18.35, 2.73627), (25.45, 18.35, 2.92598), (26.45, 18.35, 3.14411), (27.45, 18.35, 3.26676), (28.45, 18.35, 3.3058), (29.45, 18.35, 3.42846), (30.45, 18.35, 3.87435), (31.45, 18.35, 3.79691), (32.45, 18.35, 4.32757), (34.45, 18.35, 3.45052), (35.45, 18.35, 3.8118), (36.45, 18.35, 3.41027), (37.45, 18.35, 3.25379), (38.45, 18.35, 3.23332), (3.45, 17.35, 4.7064), (4.45, 17.35, 4.371), (5.45, 17.35, 4.75561), (6.45, 17.35, 4.76649), (7.45, 17.35, 4.21778), (9.45, 17.35, 2.28275), (13.45, 17.35, 2.29932), (14.45, 17.35, 2.36372), (15.45, 17.35, 2.48865), (17.45, 17.35, 2.66335), (18.45, 17.35, 2.66399), (19.45, 17.35, 3.77525), (23.45, 17.35, 1.85281), (24.45, 17.35, 2.29106), (25.45, 17.35, 2.66281), (26.45, 17.35, 2.71972), (27.45, 17.35, 2.9974), (28.45, 17.35, 3.28362), (29.45, 17.35, 3.54962), (30.45, 17.35, 3.71915), (31.45, 17.35, 3.98101), (32.45, 17.35, 3.93729), (33.45, 17.35, 3.32809), (34.45, 17.35, 3.50216), (35.45, 17.35, 3.29357), (36.45, 17.35, 3.19157), (37.45, 17.35, 3.08379), (38.45, 17.35, 2.79997), (39.45, 17.35, 3.98653), (3.45, 16.35, 4.5621), (4.45, 16.35, 5.06523), (5.45, 16.35, 5.0213), (6.45, 16.35, 4.77832), (13.45, 16.35, 1.91334), (14.45, 16.35, 1.99385), (17.45, 16.35, 2.42404), (18.45, 16.35, 2.46178), (19.45, 16.35, 3.46624), (20.45, 16.35, 3.83212), (23.45, 16.35, 1.78153), (24.45, 16.35, 1.84322), (25.45, 16.35, 2.41425), (29.45, 16.35, 3.75496), (30.45, 16.35, 4.16121), (31.45, 16.35, 4.1209), (32.45, 16.35, 3.72046), (33.45, 16.35, 3.47978), (34.45, 16.35, 3.61712), (35.45, 16.35, 3.41975), (36.45, 16.35, 3.11658), (37.45, 16.35, 2.84706), (38.45, 16.35, 3.04406), (39.45, 16.35, 4.12565), (40.45, 16.35, 3.98176), (3.45, 15.35, 4.28908), (4.45, 15.35, 5.22428), (5.45, 15.35, 5.19235), (6.45, 15.35, 4.77923), (12.45, 15.35, 2.64493), (13.45, 15.35, 1.22772), (14.45, 15.35, 1.51841), (20.45, 15.35, 3.99188), (21.45, 15.35, 3.37888), (22.45, 15.35, 2.5993), (23.45, 15.35, 1.87389), (24.45, 15.35, 1.60633), (29.45, 15.35, 5.28181), (30.45, 15.35, 5.16979), (31.45, 15.35, 4.67128), (32.45, 15.35, 3.80629), (33.45, 15.35, 3.42772), (34.45, 15.35, 3.79347), (35.45, 15.35, 3.67072), (36.45, 15.35, 3.02288), (37.45, 15.35, 2.73436), (38.45, 15.35, 3.18135), (39.45, 15.35, 4.02025), (40.45, 15.35, 3.96093), (41.45, 15.35, 4.01929), (42.45, 15.35, 4.30221), (3.45, 14.35, 4.25945), (4.45, 14.35, 5.32842), (5.45, 14.35, 5.30354), (13.45, 14.35, 0.884203), (14.45, 14.35, 0.776718), (15.45, 14.35, 0.562447), (16.45, 14.35, 0.44932), (17.45, 14.35, 0.452077), (18.45, 14.35, 0.514346), (19.45, 14.35, 0.647639), (20.45, 14.35, 2.17445), (21.45, 14.35, 3.23923), (22.45, 14.35, 3.14658), (23.45, 14.35, 3.06958), (24.45, 14.35, 2.32319), (25.45, 14.35, 1.38573), (28.45, 14.35, 5.71052), (29.45, 14.35, 5.21399), (33.45, 14.35, 3.35032), (34.45, 14.35, 4.02932), (35.45, 14.35, 3.98167), (36.45, 14.35, 2.93596), (37.45, 14.35, 2.32492), (38.45, 14.35, 3.25625), (39.45, 14.35, 4.07215), (40.45, 14.35, 3.91543), (41.45, 14.35, 3.98522), (42.45, 14.35, 4.47266), (3.45, 13.35, 4.22955), (4.45, 13.35, 5.42547), (14.45, 13.35, 0.798981), (15.45, 13.35, 0.371203), (16.45, 13.35, 0.363399), (17.45, 13.35, 0.359497), (18.45, 13.35, 0.432276), (19.45, 13.35, 0.574261), (20.45, 13.35, 0.654132), (21.45, 13.35, 1.0864), (22.45, 13.35, 3.40516), (23.45, 13.35, 5.18029), (24.45, 13.35, 5.16315), (25.45, 13.35, 4.69197), (26.45, 13.35, 1.65828), (27.45, 13.35, 4.02412), (34.45, 13.35, 4.36814), (35.45, 13.35, 4.17758), (37.45, 13.35, 1.8505), (38.45, 13.35, 2.97452), (39.45, 13.35, 3.52383), (40.45, 13.35, 3.64515), (41.45, 13.35, 4.41255), (42.45, 13.35, 4.42249), (3.45, 12.35, 4.17467), (15.45, 12.35, 1.01666), (16.45, 12.35, 0.516123), (17.45, 12.35, 0.940845), (18.45, 12.35, 0.479236), (19.45, 12.35, 0.821501), (20.45, 12.35, 0.748288), (21.45, 12.35, 0.439029), (22.45, 12.35, 4.74225), (23.45, 12.35, 6.18834), (24.45, 12.35, 5.55127), (25.45, 12.35, 1.25603), (26.45, 12.35, 1.40938), (27.45, 12.35, 2.89496), (28.45, 12.35, 0.658806), (29.45, 12.35, 2.73886), (30.45, 12.35, 4.88929), (34.45, 12.35, 4.90631), (35.45, 12.35, 4.92355), (37.45, 12.35, 1.40375), (38.45, 12.35, 1.64538), (39.45, 12.35, 2.7691), (40.45, 12.35, 4.50524), (41.45, 12.35, 4.62781), (42.45, 12.35, 4.48682), (43.45, 12.35, 4.54338), (46.45, 12.35, 1.0499), (47.45, 12.35, 1.33786), (2.45, 11.35, 4.50815), (3.45, 11.35, 3.76135), (18.45, 11.35, 3.00127), (19.45, 11.35, 0.237008), (20.45, 11.35, 0.729628), (21.45, 11.35, 0.26128), (22.45, 11.35, 4.42975), (23.45, 11.35, 6.10986), (24.45, 11.35, 1.65615), (25.45, 11.35, 0.658839), (26.45, 11.35, 0.770529), (27.45, 11.35, 5.54373), (28.45, 11.35, 0.983077), (29.45, 11.35, 0.160647), (30.45, 11.35, 0.154399), (31.45, 11.35, 1.30216), (32.45, 11.35, 3.41579), (33.45, 11.35, 5.43441), (34.45, 11.35, 5.68538), (35.45, 11.35, 5.46175), (37.45, 11.35, 0.924759), (38.45, 11.35, 1.35731), (39.45, 11.35, 2.39494), (40.45, 11.35, 4.89447), (41.45, 11.35, 4.75325), (42.45, 11.35, 4.73094), (43.45, 11.35, 4.63161), (47.45, 11.35, 1.72406), (2.45, 10.35, 4.1519), (3.45, 10.35, 3.37614), (18.45, 10.35, 5.19059), (20.45, 10.35, 3.62262), (21.45, 10.35, 5.41243), (22.45, 10.35, 5.92728), (23.45, 10.35, 3.99086), (24.45, 10.35, 0.992473), (25.45, 10.35, 0.318592), (26.45, 10.35, 1.28979), (27.45, 10.35, 5.20035), (28.45, 10.35, 4.31644), (29.45, 10.35, 0.148998), (30.45, 10.35, 0.20442), (31.45, 10.35, 0.255285), (32.45, 10.35, 1.54759), (33.45, 10.35, 6.01959), (34.45, 10.35, 6.07745), (35.45, 10.35, 5.67771), (36.45, 10.35, 3.68422), (37.45, 10.35, 0.643142), (38.45, 10.35, 0.906796), (39.45, 10.35, 2.31807), (40.45, 10.35, 5.04033), (41.45, 10.35, 4.9481), (42.45, 10.35, 4.9229), (46.45, 10.35, 2.08466), (2.45, 9.35, 4.37446), (3.45, 9.35, 2.37878), (7.45, 9.35, 4.5364), (22.45, 9.35, 5.42963), (23.45, 9.35, 2.89403), (24.45, 9.35, 0.891453), (25.45, 9.35, 1.6401), (26.45, 9.35, 4.61513), (27.45, 9.35, 5.89944), (28.45, 9.35, 6.05797), (29.45, 9.35, 0.651896), (30.45, 9.35, 0.285114), (31.45, 9.35, 0.986258), (32.45, 9.35, 5.40265), (33.45, 9.35, 6.21104), (34.45, 9.35, 5.76166), (35.45, 9.35, 3.69621), (36.45, 9.35, 4.00774), (37.45, 9.35, 0.611598), (38.45, 9.35, 0.599693), (39.45, 9.35, 3.29456), (40.45, 9.35, 5.76694), (41.45, 9.35, 5.19357), (42.45, 9.35, 5.06682), (46.45, 9.35, 2.18048), (2.45, 8.35, 4.09756), (3.45, 8.35, 1.80292), (7.45, 8.35, 4.70647), (24.45, 8.35, 1.88445), (26.45, 8.35, 6.02448), (27.45, 8.35, 6.09969), (28.45, 8.35, 5.80012), (29.45, 8.35, 1.48522), (30.45, 8.35, 1.04692), (31.45, 8.35, 2.32415), (32.45, 8.35, 3.73526), (33.45, 8.35, 6.01437), (34.45, 8.35, 5.70116), (35.45, 8.35, 6.08849), (36.45, 8.35, 2.18194), (37.45, 8.35, 0.865276), (38.45, 8.35, 0.75228), (39.45, 8.35, 5.415), (40.45, 8.35, 5.79797), (41.45, 8.35, 5.65342), (42.45, 8.35, 5.41216), (2.45, 7.35, 3.54502), (3.45, 7.35, 1.67152), (4.45, 7.35, 1.66108), (6.45, 7.35, 4.65899), (7.45, 7.35, 4.78321), (37.45, 7.35, 1.65549), (38.45, 7.35, 3.45196), (39.45, 7.35, 5.47972), (40.45, 7.35, 5.7046), (52.45, 7.35, 3.08766), (1.45, 6.35, 4.68454), (2.45, 6.35, 3.21162), (3.45, 6.35, 1.64639), (4.45, 6.35, 1.73195), (7.45, 6.35, 4.50525), (37.45, 6.35, 2.01563), (38.45, 6.35, 4.11893), (39.45, 6.35, 5.47254), (52.45, 6.35, 4.36276), (1.45, 5.35, 4.73421), (2.45, 5.35, 2.58446), (3.45, 5.35, 1.69313), (7.45, 5.35, 4.81475), (1.45, 4.35, 4.54162), (2.45, 4.35, 1.94325), (3.45, 4.35, 2.02884), (27.45, 4.35, 1.58355), (1.45, 3.35, 3.75885), (23.45, 3.35, 5.29889), (24.45, 3.35, 5.55216), (27.45, 3.35, 4.1723), (28.45, 3.35, 0.985946), (29.45, 3.35, 1.53282), (30.45, 3.35, 4.63566), (51.45, 3.35, 5.59098), (52.45, 3.35, 5.42095), (1.45, 2.35, 3.4239), (16.45, 2.35, 4.46786), (17.45, 2.35, 5.5381), (18.45, 2.35, 5.7295), (19.45, 2.35, 5.87775), (20.45, 2.35, 5.9451), (21.45, 2.35, 5.95182), (22.45, 2.35, 5.68979), (23.45, 2.35, 5.29518), (25.45, 2.35, 4.22352), (26.45, 2.35, 3.70319), (27.45, 2.35, 3.39012), (28.45, 2.35, 2.93487), (29.45, 2.35, 2.95917), (30.45, 2.35, 2.09901), (31.45, 2.35, 2.80603), (32.45, 2.35, 4.86516), (33.45, 2.35, 4.93323), (34.45, 2.35, 4.78742), (35.45, 2.35, 4.79015), (36.45, 2.35, 4.69011), (37.45, 2.35, 4.21803), (38.45, 2.35, 4.06135), (39.45, 2.35, 3.73948), (40.45, 2.35, 3.36279), (41.45, 2.35, 3.0432), (42.45, 2.35, 2.27738), (43.45, 2.35, 2.08849), (44.45, 2.35, 1.86689), (45.45, 2.35, 1.65888), (46.45, 2.35, 1.48949), (47.45, 2.35, 2.51673), (48.45, 2.35, 4.23681), (49.45, 2.35, 4.51579), (50.45, 2.35, 4.73011), (51.45, 2.35, 4.13667), (52.45, 2.35, 3.49318)]

class CanWorker(DeviceWorker):
    def __init__(self, req_port=default_req_port, pub_port=default_pub_port, **kwargs):
        super().__init__(req_port=req_port, pub_port=pub_port, **kwargs)
        self.messages = []
        self.wheels = [0, 0, 0, 0]
        self.wheels_target = [0, 0, 0, 0]
        self.wheels_pid = False
        self.wheels_manual = False
        self.wheels_last_time_manual = clock()
        self.wheels_pid_controllers = [PID() for k in range(4)]
        self.battery_v = [0, 0, 0, 0]
        self.compass_pitch = 0.0
        self.compass_roll = 0.0
        self.compass_heading = 0.0
        self.compass_terrain_direction = 0.0
        self.compass_terrain_slope = 0.0
        self.throttle = 0.0
        self.turning = 0.0
        self.position = (24.3, 4.3)
        self.is_ik = False
        self.ikpositions = [0.85 * PI, 0.65 *PI, PI, PI]
        self.encoders = {arm_lower:0, arm_upper:0, arm_rot:0, grip_lat:0}
        self.index_pulses = {arm_lower:500.0, arm_upper:500.0, arm_rot:500.0, grip_lat:500.0}
        self.ik_position = [150 * deg, 90 * deg, 240 * deg, 180 * deg]
        self.ik_speed = [0, 0, 0, 0]
        self.ik_update_timestamp = clock()
        self.ik_watchdog_timestamp = clock() - 1
        self.air_humidity = 0
        self.air_temperature = 0
        self.air_co2 = 0
        self.soil_temperature = 0
        self.soil_humidity = 0
        self.logfile = open("vlog.txt", "a");
        self.logc = 0
        self.autonomy = Autonomy()

    def init_device(self):
        self._bus = can.interface.Bus(bustype="socketcan", channel="can0", bitrate=250000)

        self.data_lock = threading.Lock()
        self.msg_lock = threading.Lock()
        self.position_lock = threading.Lock()
        self.auto_lock = threading.Lock()
        self.ik_lock = threading.Lock()

        self.msg_thread = threading.Thread(target=self.loop_read)
        self.msg_thread.start()

        self.wheels_lock = threading.Lock()
        self.position_thread = threading.Thread(target=self.loop_position)
        self.position_thread.start()

        self.ik_thread = threading.Thread(target=self.loop_ik)
        self.ik_thread.start()

        self.serial_dht22 = serial.Serial('/dev/ttyAMA0', 115200, timeout=5)
        self.lock_dht22 = threading.Lock()
        self.thread_dht22 = threading.Thread(target=self.loop_dht22)
        self.thread_dht22.start()

        self.set_blink()
        self.blink_thread = threading.Thread(target=self.loop_blink)
        self.blink_thread.start()

        try:
            self.reach = Reach()
        except:
            self.reach = None
            print("No connection with reach.")
        self.auto_thread = threading.Thread(target=self.loop_auto)
        self.auto_thread.start()

        self.script_lock = threading.Lock()
        self.script_stop = 0
        self.script_code = ""
        self.script_thread = threading.Thread(target=self.loop_script)
        self.script_thread.start()

        self.send(128, [20,10])
        self.send(400, [100, 0, 100])

        self.servopos = [1500 for i in range(124)]
        self.servopos[0] = 1730
        self.servo(0, 1)

        #self.tag_reader = TagReader()

        self.send(arm_lower, [18, 100])
        self.send(arm_upper, [18, 100])
        self.send(grip_lat, [18, 100])
        self.send(arm_rot, [18, 100])

        print("Can initialized")


    def status(self):
        """ This function will be called periodically to monitor the state 
        of the device. It should return a dictionary describing the current
        state of the device. This dictionary will be delivered to the 
        front-end class."""
        if self.is_ik:
            self.ik(self.ik_x, self.ik_y, self.ik_a, self.ik_d)


        d = super().status()
        d["connected"] = True
        d["position"] = self.get_position()
        d["coordinates"] = self.get_coordinates()
        with self.data_lock:
            d["heading"] = self.compass_heading
            d["terrain_direction"] = self.compass_terrain_direction
            d["terrain_slope"] = self.compass_terrain_slope
            d["voltage"] = sum(self.battery_v) / 40.0
            d["encoders"] = self.encoders
            d["index_pulses"] = self.index_pulses
            d["wheels"] = self.wheels
            d["air_temperature"] = self.get_air_temperature()
            d["air_humidity"] = self.get_air_humidity()
            d["air_co2"] = self.air_co2
            d["soil_temperature"] = self.soil_temperature
            d["soil_humidity"] = self.soil_humidity

            s = sum(self.battery_v)
            if s < 4 * 180:
                i = 0
            elif s >= 4 * 252:
                i = 4 * 72 - 1
            else:
                i = s - 180 * 4

            d['battery'] = lipo_characteristics[i]

        self.logfile.write("%f\t%f\n" % (time(), sum(self.battery_v) / 40.0))
        self.logc += 1
        if self.logc % 100 == 0:
            self.logfile.flush()

        return d

        # This method is override of can.Listener method, so message is in sense of packet.

    @remote
    def read(self):
        with self.msg_lock:
            for msg in self.messages:
                print((msg.arbitration_id - 1024, list(msg.data)))
            self.messages = []

    def loop_ik(self): # function for constant speed pad arm movement with use of ik
        while True:
            with self.data_lock:
                speed = self.ik_speed
            if speed != [0, 0, 0, 0]:
                self.ik_watchdog_timestamp = clock()
            if self.ik_watchdog_timestamp + 0.5 < clock():
                self.ik_update_timestamp = clock()
                with self.data_lock:
                    self.ik_position = (self.encoders[arm_lower] * deg, self.encoders[arm_upper] * deg, self.encoders[grip_lat] * deg, self.encoders[arm_rot] * deg)
            else:
                #print("ok" + str(speed))
                position = self.ik_position
                position_arm = axes_to_arm(position)
                dt = clock() - self.ik_update_timestamp
                self.ik_update_timestamp = clock()
                position_arm_new = [position_arm[i] + speed[i] * dt for i in range(4)]
                try:
                    position_new = arm_to_axes(position_arm_new)
                    self.ik_position = position_new
                    self.ik(position_new[0:3])
                except Exception as e:
                    print(e)
            sleep(0.030)

    def loop_read(self):
        for msg in self._bus:
            if msg.arbitration_id < 1024:
                continue
            elif msg.arbitration_id >= 1024 + 140 and msg.arbitration_id <= 1024 + 143 and msg.data[0] == 30: # wheels encoder
                motor = msg.arbitration_id - 1024 - 140
                with self.msg_lock:
                    self.messages.append(msg)
                with self.data_lock:
                    self.wheels[motor] = int.from_bytes(msg.data[1:5], byteorder='big', signed=True)
                    self.battery_v[motor] = int.from_bytes(msg.data[5:7], byteorder='big', signed=True)
            elif msg.data[0] == 28: # readings from arm encoders
                motor = msg.arbitration_id - 1024
                with self.data_lock:
                    try:
                        self.index_pulses[motor] = (msg.data[3] * 256 + msg.data[4]) / 10
                    except Exception as e:
                        pass
                    self.encoders[motor] = (msg.data[1] * 256 + msg.data[2]) / 10
            elif msg.data[0] == 106:
                self.compass_heading = (list_to_int(msg.data[5:7]) * 3.14159 / 180 / 10) % (2 * PI)
                self.compass_pitch = list_to_int(msg.data[1:3])  * 3.14159 / 180 / 10
                self.compass_roll = list_to_int(msg.data[3:5])  * 3.14159 / 180 / 10
                self.compass_terrain_direction = (self.compass_heading - math.atan2(self.compass_roll, self.compass_pitch)) % (2 * PI)
                self.compass_terrain_slope = math.asin((math.sin(self.compass_pitch) ** 2 + math.cos(self.compass_pitch) ** 2 * math.sin(self.compass_roll) ** 2) ** 0.5)
            elif msg.data[0] == 80:
                self.soil_humidity = (2.56 - list_to_int(msg.data[1:3]) * 528 / 624 / 1000) / (2.56 - 1.35) * 100
                print(self.soil_humidity)
            elif msg.data[0] == 83:
                self.air_co2 =((list_to_int(msg.data[1:3]) * 528 / 624 / 1000) - 0.4) / 1.6 * 5000 #* 100 / 13.7
            else:
                with self.msg_lock:
                    self.messages.append(msg)

    @remote
    def set_pid_wheels(self, on=True, params = None):
        self.wheels_target = [v for v in self.wheels]
        if params is not None:
            for i in range(4):
                self.wheels_pid_controllers[i].set_params(params)
        self.wheels_pid = on


    def loop_position(self):
        sleep(1)
        self.last_tacho = self.tacho()
        FPS = 100
        dt = 1.0 / FPS
        last_clock = clock()
        while True:
            with self.data_lock:
                pid = self.wheels_pid
                position = self.wheels
                target = self.wheels_target
            with self.wheels_lock:
                pid = pid and clock() > self.wheels_last_time_manual + 0.5
            if pid:
                for i in range(4):
                    error = target[i] - position[i]
                    power = self.wheels_pid_controllers[i].step(dt, error)
                    self.power(140 + i, power)
            else:
                with self.data_lock:
                    self.wheels_target = [v for v in position]

            tacho = self.tacho()
            dx = tacho - self.last_tacho
            self.last_tacho = tacho
            with self.data_lock:
                heading = self.compass_heading
                self.position = (self.position[0] + math.sin(heading) * dx, self.position[1] + math.cos(heading) * dx)

            while clock() < last_clock + dt:
                pass
            last_clock = clock() + dt

    def loop_dht22(self):
        while 1:
            try:
                sleep(0.1)
                line = self.serial_dht22.readline()
                if line[0:10] == b'Sample OK:':
                    temp = float(line[10:17])
                    hum = float(line[20:27])
                #=================================
                #Sample DHT22...
                #Sample OK: 33.10 *C, 36.30 RH%
                #=================================
                    if hum is not None and temp is not None:
                        with self.lock_dht22:
                            self.air_humidity = hum
                            self.air_temperature = temp
            except Exception as e:
                print(e)

    def loop_blink(self):
        while True:
            sleep(0.5)
            if self.blink == 1:
                self.power(210, -1)
            sleep(0.5)
            self.power(210, 0)

    @remote
    def set_blink(self, on = 1):
        self.blink = on

    def loop_auto(self):
        while True:
            with self.auto_lock:
                if not self.autonomy.is_running():
                    sleep(0.5)
                    continue

                position = self.get_coordinates()
                heading = self.get_orientation()

                throttle, turning = self.autonomy.step(position, orientation)
                self.drive_both_axes(throttle, turning)

    @remote
    def start_auto_from_waypoint(self, waypoint = 0):
        with self.auto_lock:
            self.autonomy.start(waypoint)

    @remote
    def end_auto(self):
        with self.auto_lock:
            self.autonomy.halt()

    @remote
    def get_coordinates(self):
        if self.reach is not None:
            return self.reach.get_status()
        else:
            return (0, 0)

    @remote
    def get_orientation(self):
        with self.data_lock:
            o = self.compass_heading
        return o

    @remote
    def get_position(self, origin=relative_position_default_origin, axis=-1):
        coords = self.get_coordinates()
        x = (coords[1] - origin[1]) * deg * 6371000 * math.cos(coords[0] * deg)
        y = (coords[0] - origin[0]) * deg * 6371000
        if axis == 0:
            return x
        elif axis == 1:
            return y
        else:
            return (x, y)

    @remote
    def set_waypoints(self, waypoints):
        with self.auto_lock:
            self.autonomy.set_waypoints(waypoints)

    @remote
    def abort_script(self):
        with self.script_lock:
            self.script_stop = 1
            self.script_code = ""

    @remote
    def run_script(self, code):
        with self.script_lock:
            self.script_stop = 0
            self.script_code = code

    def loop_script(self):
        while True:
            def is_number(s):
                try:
                    float(s)
                    return True
                except ValueError:
                    return False

            while True:
                sleep(0.1)
                with self.script_lock:
                    code = self.script_code
                    self.script_code = ""
                if code != "":
                    break

            lines = [line.split() for line in code.split("\n")]
            print(lines)
            var_dict = {}
            functions = {}
            code_time = 0
            abort = False
            start = clock()
            for line in lines:
                if line == []:
                    continue
                line_err = str(line)
                try:
                    first = line.pop(0)
                    if is_number(first):
                        code_time += float(first)
                        while line != []:
                            command = line.pop(0)
                            if command == "x":
                                args = (float(line.pop(0)) * deg, float(line.pop(0)) * deg, float(line.pop(0)) * deg, float(line.pop(0)) * deg)
                                functions["__ik__"] = lambda args=args : self.ik(args)
                            elif command == "a":
                                args = (float(line.pop(0)), float(line.pop(0)), float(line.pop(0)) * deg, float(line.pop(0)) * deg)
                                functions["__ik__"] = lambda args=args: self.ik(arm_to_axes(args))
                            elif command == "r":
                                args = (float(line.pop(0)), float(line.pop(0)), float(line.pop(0)), float(line.pop(0)) * deg)
                                functions["__ik__"] = lambda args=args: self.ik(rover_to_axes(args))
                            elif command == "apply_index":
                                self.apply_index()
                            else:
                                if is_number(command):
                                    motor = int(command)
                                else:
                                    motor = var_dict[command]
                                power = float(line.pop(0))
                                if abs(power) < 0.000001:
                                    self.power(motor, 0)
                                    functions[motor] = lambda: None
                                else:
                                    functions[motor] = lambda motor=motor, power=power: self.power(motor, power)

                    else:
                        var_dict[first] = int(line.pop(0))

                    while clock() < start + code_time:  # sync with code_time
                        for key in functions:
                            functions[key]()
                        towait = max(0, min(0.1, start + code_time - clock()))
                        sleep(towait)
                        with self.script_lock:
                            if self.script_stop == 1:
                                self.script_stop = 0
                                abort = True
                        if abort:
                            print("abort")
                            break
                except Exception as e:
                    print(str(e) + " while processing line " + line_err)
                    break
                if abort:
                    break

    @remote
    def fix_pos(self, x, y):
        self.position = (x, y)

    @remote
    def servo(self, id, move):
        self.servopos[id] += move
        if self.servopos[id] > 2500:
            self.servopos[id] = 2500
        if self.servopos[id] < 500:
            self.servopos[id] = 500
        if id // 8 == 0:
            self.send(306, [5, id % 8, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
        if id // 8 == 1:
            self.send(305, [5, id % 8, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
        if id // 8 == 2:
            self.send(307, [5, id % 8, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
        if id == 101:
            self.send(305, [5, 0, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
            self.send(305, [5, 1, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
            self.send(305, [5, 2, int(3000-self.servopos[id]) >> 8, int(3000-self.servopos[id]) & 0xff])
            self.send(305, [5, 3, int(3000-self.servopos[id]) >> 8, int(3000-self.servopos[id]) & 0xff])
        if id == 100:
            self.send(305, [5, 4, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])
            self.send(305, [5, 5, int(self.servopos[id]) >> 8, int(self.servopos[id]) & 0xff])



    @remote
    def servo_pos(self, id, pos):
        if id // 8 == 0:
            self.send(306, [5, id % 8, int(pos) >> 8, int(pos) & 0xff])
        if id // 8 == 1:
            self.send(305, [5, id % 8, int(pos) >> 8, int(pos) & 0xff])
        if id // 8 == 2:
            self.send(307, [5, id % 8, int(pos) >> 8, int(pos) & 0xff])
        if id == 101:
            self.send(305, [5, 0, int(pos) >> 8, int(pos) & 0xff])
            self.send(305, [5, 1, int(pos) >> 8, int(pos) & 0xff])
            self.send(305, [5, 2, int(3000 - pos) >> 8, int(3000 - pos) & 0xff])
            self.send(305, [5, 3, int(3000 - pos) >> 8, int(3000 - pos) & 0xff])
        if id == 100:
            self.send(305, [5, 4, int(pos) >> 8, int(pos) & 0xff])
            self.send(305, [5, 5, int(pos) >> 8, int(pos) & 0xff])

    @remote
    def servos(self):
        return [("servo_306:" + str(i%8), i) for i in range(0, 8)] + \
               [("servo_305:" + str(i%8), i) for i in range(8, 16)] + \
               [("servo_307:" + str(i%8), i) for i in range(16, 24)] + \
               [("arm_upper: 100", 100), ("grip_clamp: 101", 101)]

    @remote
    def tags(self):
        list = [None for i in range(35)]
        markers = []# self.tag_reader.get_markers()
        for i, data in markers:
            print(i, data)
            d0 = float(data[0])
            d2 = float(data[2])
            with self.data_lock:
                a = (math.atan2(d0, d2) + self.compass_heading) % (2 * PI)
            r = (d0 ** 2 + d2 ** 2) ** 0.5
            print(a, r, i)
            list[int(i)] = (a, r)
        return list

    @remote
    def slope_points(self):
        with self.data_lock:
            slope = self.compass_terrain_slope
            direction = self.compass_terrain_direction
        if slope > 12 / 180 * PI:
            return([(t[0], t[1]) for t in slopepoints if abs((t[2] - direction + PI) % (2 * PI) - PI) < PI / 6])
        else:
            return []

    @remote
    def tacho(self):
        with self.data_lock:
            return 0.5 * (self.wheels[1] - self.wheels[3]) / erpm_per_meter

    @remote
    def send(self, id, data):
        print("send")
        self._bus.send(can.Message(arbitration_id=id, data = data, extended_id = False))

    @remote
    def start_ik(self):
        alfa = 796 + 900
        beta = 1253
        self.send(arm_lower, [38, alfa >> 8, alfa & 0xff])
        self.send(arm_upper, [38, beta >> 8, beta & 0xff])
        self.send(grip_lat, [38, 1800 >> 8, 1800 & 0xff])
        self.send(arm_rot, [38, 1800 >> 8, 1800 & 0xff])

    @remote
    def apply_index(self):
        def set(motor, angle):
            a = int(angle * 10)
            if a < 0:
                a = 0
            if a >= 3600:
                a = 3599
            self.send(motor, [38, a >> 8, a & 0xff])
        set(arm_lower, self.encoders[arm_lower] + 153.8 - self.index_pulses[arm_lower])
        set(arm_upper, self.encoders[arm_upper] + 117.7 - self.index_pulses[arm_upper])
        set(grip_lat, self.encoders[grip_lat] + 152.0 - self.index_pulses[grip_lat])
        set(arm_rot, self.encoders[arm_rot] + 200.0 - self.index_pulses[arm_rot])

    @remote
    def get_encoders(self):
        return self.encoders

    @remote
    def get_index_pulses(self):
        return self.index_pulses

    @remote
    def set_ik(self, on = True):
        self.is_ik = on

    @remote
    def ik_deg(self, tx, ty, ta, td):
        self.ik(tx, ty, ta * PI / 180, td * PI / 180)

    @remote
    def ik(self, params): # execute given goal angles - send to motor drivers
        if len(params) == 4:
            outa, outb, outc, outd = [int((v % (2 * PI)) * 1800 / PI) for v in params]
            self._bus.send(can.Message(arbitration_id=int(arm_lower),
                                        data=[8, (outa >> 8) & 0xff, outa & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(arm_upper),
                                        data=[8, (outb >> 8) & 0xff, outb & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(grip_lat),
                                        data=[8, (outc >> 8) & 0xff, outc & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(arm_rot),
                                        data=[8, (outd >> 8) & 0xff, outd & 0xff], extended_id=False))
        else: # without arm rotation
            outa, outb, outc = [int((v % (2 * PI)) * 1800 / PI) for v in params]
            self._bus.send(can.Message(arbitration_id=int(arm_lower),
                                       data=[8, (outa >> 8) & 0xff, outa & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(arm_upper),
                                       data=[8, (outb >> 8) & 0xff, outb & 0xff], extended_id=False))
            self._bus.send(can.Message(arbitration_id=int(grip_lat),
                                       data=[8, (outc >> 8) & 0xff, outc & 0xff], extended_id=False))
    @remote
    def ik_arm(self, params):
        print(params)
        print(arm_to_axes(params))
        self.ik(arm_to_axes(params))

    @remote
    def ik_rover(self, params):
        self.ik(rover_to_axes(params))

    @remote
    def power(self, id, power):
        power = float(power)
        if id >= 2000 and id <= 2001:
            self.ik_speed[id - 2000] = power
        elif id >= 2002 and id <= 2003:
            self.ik_speed[id - 2000] = power * deg
        else:
            if power < -1:
                power = - 1
            if power > 1:
                power = 1
            out = round((2 ** 15 - 1) * power)
            if out < 0:
                   out += 2 ** 16
            self._bus.send(can.Message(arbitration_id=int(id), data=[7, out >> 8, out & 0xff], extended_id=False))

    @remote
    def drive(self, axis, power):
        print("drive")
        if axis == 0: #throttle
            self.throttle = power
        if axis == 1: #turning
            self.turning = power

        with self.wheels_lock:
            if abs(self.throttle) + abs(self.turning) > 0.000001:
                self.wheels_last_time_manual = clock()
        left = -self.throttle + self.turning
        right = -self.throttle - self.turning

        self.power(129, left)
        self.power(130, right)

    @remote
    def drive_both_axes(self, throttle, turning):
        self.drive(0, throttle)
        self.drive(1, turning)

    @remote
    def axes(self):
        return [
                   ("wheels_left", 129),
                   ("wheels_right", 130),
                   ("arm_rot", arm_rot),
                   ("arm_lower", arm_lower),
                   ("arm_upper", arm_upper),
                   ("grip_lat", grip_lat),
                   ("grip_rot", 192),
                   ("grip_clamp", 193),
                   ("blinker", 210)
               ] \
               + [
                   ("arm_ik_forward", 2000),
                   ("arm_ik_up", 2001),
                   ("arm_ik_grip", 2002),
                   ("arm_ik_left", 2003)
               ] \
               + [("wheel_" + str(i - 140), i) for i in range(140, 144)] \
               + [("", i) for i in range(194, 200)] \
               + [("", i) for i in range(202, 210)]

    @remote
    def get_air_temperature(self):
        with self.lock_dht22:
            return round(self.air_temperature, 2)

    @remote
    def get_air_humidity(self):
        with self.lock_dht22:
            return round(self.air_humidity, 2)


    
@include_remote_methods(CanWorker)
class Can(DeviceOverZeroMQ):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def createDock(self, parentWidget, menu=None):
        dock = QtWidgets.QDockWidget("Dummy device", parentWidget)
        widget = QtWidgets.QWidget(parentWidget)
        layout = QtWidgets.QHBoxLayout(parentWidget)
        widget.setLayout(layout)
        vwidget = QtWidgets.QWidget()
        layout_imu = QtWidgets.QGridLayout(vwidget)
        layout_sensors = QtWidgets.QGridLayout(vwidget)
        layout.addWidget(vwidget)
        layout.addLayout(layout_sensors)
        self.button_send = QtWidgets.QPushButton("SEND", parentWidget)

        self.battery_bar = QtWidgets.QProgressBar()
        self.battery_bar.setOrientation(QtCore.Qt.Vertical)
        self.battery_bar.setRange(0,100)
        self.battery_bar.setTextVisible(True)
        self.battery_label = QtWidgets.QLabel()
        self.battery_label.setFixedWidth(45)
        layout.addWidget(self.battery_label)
        layout.addWidget(self.battery_bar)
        self.edits = []
        self.edits_sensors = []
        self.edits_encoder_position = []
        self.edits_index_pulses_positions = []
        self.editswheels = []
        self.labels_encoders = []
        for i in range(3):
            edit = QtWidgets.QLineEdit()
            edit.setFixedWidth(100)
            layout_imu.addWidget(QtWidgets.QLabel(["Azimuth", "Terrain azimuth", "Terrain slope"][i]), i, 0)
            layout_imu.addWidget(edit, i, 1)
            self.edits.append(edit)

        for i in range(5):
            edit = QtWidgets.QLineEdit()
            edit.setFixedWidth(100)
            layout_sensors.addWidget(QtWidgets.QLabel(["Air temp.", "Air hum.", "Air co2 (ppm)", "Soil temp.", "Soil hum."][i]), i, 0)
            layout_sensors.addWidget(edit, i, 1)
            self.edits_sensors.append(edit)

        ewidget = QtWidgets.QWidget()
        elayout = QtWidgets.QGridLayout(ewidget)
        layout.addWidget(ewidget)

        for i in range(4):
            editwheel = QtWidgets.QLineEdit()
            editwheel.setFixedWidth(45)
            elayout.addWidget(editwheel, i, 0)
            self.editswheels.append(editwheel)
            labelenc = QtWidgets.QLabel("None")
            elayout.addWidget(labelenc, i, 1)
            self.labels_encoders.append(labelenc)
            editenc = QtWidgets.QLineEdit()
            editenc.setFixedWidth(45)
            elayout.addWidget(editenc, i, 2)
            self.edits_encoder_position.append(editenc)
            editind = QtWidgets.QLineEdit()
            editind.setFixedWidth(45)
            elayout.addWidget(editind, i, 3)
            self.edits_index_pulses_positions.append(editind)

        pidwidget = QtWidgets.QWidget()
        pidlayout = QtWidgets.QVBoxLayout(pidwidget)
        layout.addWidget(pidwidget)

        self.button_pid = QtWidgets.QPushButton("Lock Wheels")
        pidlayout.addWidget(self.button_pid)
        self.button_pid.clicked.connect(self.lock_pid)
        self.button_pid.setCheckable(True)
        self.pid_locked = False

        layout_position = QtWidgets.QVBoxLayout()
        self.edit_position_x = QtWidgets.QLineEdit()
        self.edit_position_x.setFixedWidth(90)
        self.edit_position_y= QtWidgets.QLineEdit()
        self.edit_position_y.setFixedWidth(90)
        layout_position.addWidget(self.edit_position_x)
        layout_position.addWidget(self.edit_position_y)
        layout_position.addStretch(1)
        layout.addLayout(layout_position)
        layout.addStretch(1)

        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        parentWidget.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
        if menu:
            menu.addAction(dock.toggleViewAction())
            
        # Following lines "turn on" the widget operation
        #self.increaseVoltageButton.clicked.connect(lambda pressed: self.incVoltage())
        self.createListenerThread(self.updateSlot)

    def lock_pid(self):
        if self.pid_locked:
            self.pid_locked = False
            self.button_pid.setDown(False)
            self.set_pid_wheels(0)
        else:
            self.pid_locked = True
            self.button_pid.setDown(True)
            self.set_pid_wheels(1)

        
    def updateSlot(self, status):
        self.edits_sensors[0].setText(str(round(status["air_temperature"], 2)))
        self.edits_sensors[1].setText(str(round(status["air_humidity"], 2)))
        self.edits_sensors[2].setText(str(round(status["air_co2"], 2)))
        self.edits_sensors[3].setText(str(round(status["soil_temperature"], 2)))
        self.edits_sensors[4].setText(str(round(status["soil_humidity"], 2)))
        self.edits[0].setText(str(round(status["heading"] / deg, 2)))
        self.edits[1].setText(str(round(status["terrain_direction"] / deg, 2)))
        self.edits[2].setText(str(round(status["terrain_slope"] / deg, 2)))
        self.battery_bar.setValue(status["battery"])
        self.battery_label.setText(str(status["battery"]) + '%\n' + str(round(status["voltage"], 2)) + ' V\n' + str(round(status["voltage"] / 6, 2)) + ' V\n')
        self.edit_position_x.setText(str(round(status["position"][0], 2)))
        self.edit_position_y.setText(str(round(status["position"][1], 2)))

        for i in range(4):
            self.editswheels[i].setText(str(status["wheels"][i]))
        motors = list(status["encoders"].keys())
        motors.sort()
        for i in range(4):
            self.labels_encoders[i].setText("arm axis " + str(motors[i]))
            self.edits_encoder_position[i].setText(str(status["encoders"][motors[i]]))
            self.edits_index_pulses_positions[i].setText(str(status["index_pulses"][motors[i]]))


    def send_from_gui(self):
        print(self.edits[0].text())
        print(self.edits[1].text())
        self.power(self.edits[0].text(), self.edits[1].text())

    #def get_position(self, axis):
    #    #with self.data_lock:
    #    return axis