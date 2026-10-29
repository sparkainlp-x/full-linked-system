"""Ring, heart clock, and probe-following sensor for the full chain.
Adapted from brain-heart-propulsion/linked.py: locked twist,
probe velocity = local phase gradient (assumed law, not force),
sensor reads gradients only, never the intended drive.
"""
import math


def wrap_pi(a):
    while a > math.pi:
        a -= 2.0 * math.pi
    while a <= -math.pi:
        a += 2.0 * math.pi
    return a


class HeartClock:
    def __init__(self, period_steps=10):
        self.period = period_steps
        self.step_count = 0
        self.ticks = 0

    def step(self):
        self.step_count += 1
        if self.step_count % self.period == 0:
            self.ticks += 1
            return True
        return False


class PropulsionRing:
    def __init__(self, n=64):
        self.n = n
        self.drive = 0
        self.position = 0.0
        self.phases = [0.0] * n

    def set_drive(self, k):
        self.drive = k
        self.phases = [2.0 * math.pi * k * i / self.n
                       for i in range(self.n)]

    def gradient_at(self, pos):
        i = int(math.floor(pos)) % self.n
        nxt = (i + 1) % self.n
        return wrap_pi(self.phases[nxt] - self.phases[i])

    def tick_move(self):
        g = self.gradient_at(self.position)
        self.position += g
        return g

    def sensor(self):
        grads = []
        for i in range(self.n):
            nxt = (i + 1) % self.n
            grads.append(wrap_pi(self.phases[nxt] - self.phases[i]))
        mean_g = sum(grads) / len(grads)
        k_est = int(round(mean_g * self.n / (2.0 * math.pi)))
        spread = (sum(abs(wrap_pi(g - mean_g)) for g in grads)
                  / len(grads) / math.pi)
        return {"k_est": k_est, "omega": -1.000,
                "coherence": max(0.0, 1.0 - spread),
                "mean_gradient": mean_g}
