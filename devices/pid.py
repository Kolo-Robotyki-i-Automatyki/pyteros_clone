
from collections import deque

import itertools

class PID():
    def __init__(self, params=[0.004, 10, 0]):
        self.set_params(params)
        self.integral = 0
        self.lastvals = deque([0 for i in range(1001)])

    def set_params(self, params):
        self.Ap = params[0]
        self.Fi = params[1]
        self.Td = params[2]

    def step(self, dt, error):
        N = 20
        deriv = (error - self.lastvals[9]) / (10 * dt)
        self.integral = sum(list(itertools.islice(self.lastvals, 0, 100 + 1))) / (100 + 1) * dt
        self.lastvals.rotate(1)
        self.lastvals[0] = error
        power = self.Ap * (error + deriv * self.Td + self.integral * self.Fi)

        if power > 0.35:
            power = 0.35
        if power < -0.35:
            power = -0.35
        return power