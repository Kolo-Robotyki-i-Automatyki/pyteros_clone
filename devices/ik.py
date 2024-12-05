from math import sin, cos, acos, asin, sqrt, atan2
from scipy import optimize
from time import perf_counter as clock

PI = 3.1415926536
d = PI / 180

x0 = 305.
y0 = 98.
z0 = 64.
L1 = 602.
L2 = 479.
L3 = 220.

def benchmark():
    rov = axes_to_arm([45 * d, 90 * d, 215 * d, 180 * d])
    c=clock()
    for i in range(100):
        fit = arm_to_axes(rov)
    diff = clock() - c
    print([[v / d for v in fit], diff])


def axes_to_arm(params):
    alfa, beta, gamma, delta = params
    p = L3 * sin(alfa + beta + gamma) + L2 * sin(PI + alfa + beta) + L1 * sin(alfa)
    q = - L3 * cos(alfa + beta + gamma) - L2 * cos(PI + alfa + beta) - L1 * cos(alfa)
    r = (alfa + beta + gamma + PI / 2) % (2 * PI)
    s = delta
    return (p, q, r, s)

def arm_to_axes(params):
    p, q, r, s = params
    if p < 0:
        raise ValueError('p cannot be negative')
    #alfa = PI / 2 - atan2( - ((L1 * (L1**2 * q - L2**2 * q + 2 * L3**2 * q + p**2 * q + q**3 + 2 * L3 * p * q * cos(r) - L3**2 * q * cos(2 * r) + L1**2 * L3 * sin(r) - L2**2 * L3 * sin(r) + L3**3 * sin(r) + L3 * p**2 * sin(r) + 3 * L3 * q**2 * sin(r) + L3**2 * p * sin(2 * r) - sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r))))))/(L3**2 + p**2 + q**2 + 2 * L3 * p * cos(r) + 2 * L3 * q * sin(r))),(L1 * (L1**2 * p**2 - L2**2 * p**2 + p**4 + p**2 * q**2 + 4 * L3**3 * p * cos(r)**3 + L3**4 * cos(r)**4 + 2 * L3 * p**2 * q * sin(r) + L3**2 * p**2 * sin(r)**2 + 2 * L3 * p * cos(r) * (L1**2 - L2**2 + 2 * p**2 + q**2 + 2 * L3 * q * sin(r)) + L3**2 * cos(r)**2 * (L1**2 - L2**2 + 6 * p**2 + q**2 + 2 * L3 * q * sin(r) + L3**2 * sin(r)**2) + L3**3 * p * sin(r) * sin(2 * r) + q * sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r)))) + L3 * sin(r) * sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r))))))/((p + L3 * cos(r)) * (L3**2 + p**2 + q**2 + 2 * L3 * p * cos(r) + 2 * L3 * q * sin(r))))
    #beta = PI / 2 - atan2(L1 * (L1**2 + L2**2 - L3**2 - p**2 - q**2 - 2 * L3 * p * cos(r) - 2 * L3 * q * sin(r)), - ((L1 * sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r)))))/(p + L3 * cos(r))))
    alfa = PI / 2 - atan2( - ((L1 * (L1**2 * q - L2**2 * q + 2 * L3**2 * q + p**2 * q + q**3 + 2 * L3 * p * q * cos(r) - L3**2 * q * cos(2 * r) + L1**2 * L3 * sin(r) - L2**2 * L3 * sin(r) + L3**3 * sin(r) + L3 * p**2 * sin(r) + 3 * L3 * q**2 * sin(r) + L3**2 * p * sin(2 * r) + sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r))))))/(L3**2 + p**2 + q**2 + 2 * L3 * p * cos(r) + 2 * L3 * q * sin(r))),(L1 * (L1**2 * L3**2 - L2**2 * L3**2 + L3**4 + 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 7 * L3**2 * p**2 + 2 * p**4 + L3**2 * q**2 + 2 * p**2 * q**2 + L3 * p * (4 * L1**2 - 4 * L2**2 + 7 * L3**2 + 8 * p**2 + 4 * q**2) * cos(r) + L1**2 * L3**2 * cos(2 * r) - L2**2 * L3**2 * cos(2 * r) + L3**4 * cos(2 * r) + 5 * L3**2 * p**2 * cos(2 * r) + L3**2 * q**2 * cos(2 * r) + L3**3 * p * cos(3 * r) + L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3**2 * p * q * sin(2 * r) - 2 * q * sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r)))) - 2 * L3 * sin(r) * sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r)))) + L3**3 * q * sin(3 * r)))/(2 * (p + L3 * cos(r)) * (L3**2 + p**2 + q**2 + 2 * L3 * p * cos(r) + 2 * L3 * q * sin(r))))
    beta = PI / 2 - atan2(L1 * (L1**2 + L2**2 - L3**2 - p**2 - q**2 - 2 * L3 * p * cos(r) - 2 * L3 * q * sin(r)),(L1 * sqrt( - ((p + L3 * cos(r))**2 * (L1**4 - 2 * L1**2 * L2**2 + L2**4 - 2 * L1**2 * L3**2 - 2 * L2**2 * L3**2 + L3**4 - 2 * L1**2 * p**2 - 2 * L2**2 * p**2 + 4 * L3**2 * p**2 + p**4 - 2 * L1**2 * q**2 - 2 * L2**2 * q**2 + 4 * L3**2 * q**2 + 2 * p**2 * q**2 + q**4 + 4 * L3 * p * ( - L1**2 - L2**2 + L3**2 + p**2 + q**2) * cos(r) + 2 * L3**2 * (p**2 - q**2) * cos(2 * r) - 4 * L1**2 * L3 * q * sin(r) - 4 * L2**2 * L3 * q * sin(r) + 4 * L3**3 * q * sin(r) + 4 * L3 * p**2 * q * sin(r) + 4 * L3 * q**3 * sin(r) + 4 * L3**2 * p * q * sin(2 * r)))))/(p + L3 * cos(r)))
    gamma = (- alfa - beta - PI / 2 + r) % (2 * PI)
    delta = s
    return (alfa, beta, gamma, delta)

def axes_to_rover(params):
    alfa, beta, gamma, delta = params
    x = x0 - sin(delta) * (L3 * cos(alfa + beta + gamma) - L2 * cos(alfa + beta) + L1 * cos(alfa))
    y = -y0 - cos(delta) * (L3 * cos(alfa + beta + gamma) - L2 * cos(alfa + beta) + L1 * cos(alfa))
    z = L3 * sin(alfa + beta + gamma) - L2 * sin(alfa+beta) + L1 * sin(alfa) + z0
    theta = (alfa + beta + gamma - PI) % (2 * PI)
    return (x, y, z, theta)

def arm_to_rover(params):
    p, q, r, s = params
    x = x0 - p * sin(s)
    y = -y0 - p * cos(s)
    z = q + z0
    theta = r
    return (x, y, z, theta)

def axes_to_rover(params):
    return arm_to_rover(axes_to_arm(params))

def rover_to_axes(params):
    return arm_to_axes(rover_to_arm(params))

def rover_to_arm(params):
    x, y, z, theta = params
    p = (1.0057642 * 10**7 + x * ( - 59780. - 610. * y) + 121837. * y + 294. * y**2 + y**3 + x**2 * (98. + y))/((98. + y) * sqrt(102629. - 610. * x + x**2 + 196. * y + y**2))
    q =  - 64. + z
    r = theta
    s = atan2((29890. + x * ( - 98. - 1. * y) + 305. * y)/((98. + y) * sqrt(102629. - 610. * x + x**2 + 196. * y + y**2)), - ((98. + y)/sqrt(102629. - 610. * x + x**2 + 196. * y + y**2))) % (2 * PI)
    return (p, q, r, s)
'''
def goback(arm):
    arm0 = arm
    #print([v/d for v in arm0])
    arm = axes_to_arm(arm)
    arm1=arm
    #print([arm[0], arm[1], arm[2], arm[3]/d])
    arm = arm_to_rover(arm)
    #print([arm[0], arm[1], arm[2], arm[3]/d])
    arm = rover_to_arm(arm)
    arm2 = arm
    #print([arm[0], arm[1], arm[2]/d, arm[3]/d])
    arm = arm_to_axes(arm)
    #print([v/d for v in arm0])
    #print([v/d for v in arm])

    #if abs(arm0[0] - arm[0]) > 0.001:
    #    print([v/d for v in arm0])
    #    print([arm1[0], arm1[1], arm1[2], arm1[3] / d])
    #    print([arm2[0], arm2[1], arm2[2], arm2[3] / d])
    #    print([v/d for v in arm])
    #    print("   ")

def gobackarmrover(arm):
    print([arm[0], arm[1], arm[2]/d, arm[3]/d])
    arm = arm_to_rover(arm)
    print([arm[0], arm[1], arm[2], arm[3]/d])
    arm = rover_to_arm(arm)
    print([arm[0], arm[1], arm[2]/d, arm[3]/d])
    print("   ")

from random import random as rand

for i in range(1000):
    goback((0.25 * PI + 0.75 * rand() * PI, rand() * PI, rand() * 2 * PI, rand() * 2 * PI))
    gobackarmrover((444 * rand() , rand() * 444, rand() * 2 * PI, rand() * 2*PI))
    '''