"""Full linked chain. See package README for the stage map.
nervous.py, human.py, injection.py are vendored unchanged
from membrane-nervous-system v0.2.0; lattice.py, memory.py
from microtubule-crystallize v0.1.0; lat.py from
microtubule-lattice-memory v0.1.0; ring.py adapted from
brain-heart-propulsion v0.1.0.
"""
import math
import random
import struct
import wave
import io

from nervous import MembraneNervous, noisy, rand_field
from human import modulate, sensitivity
from injection import CrystallizeInjection
from ring import HeartClock, PropulsionRing
from ledger import Ledger

RESPONSE_TO_DRIVE = {"withdraw": 1, "grasp": -1,
                     "balance": 0, "cool-alert": 0}


class FullResult:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return (f"FullResult({self.decision!r}, {self.response!r}, "
                f"drive={self.drive}, disp={self.displacement:.2f}, "
                f"sensor_k={self.sensor['k_est']}, "
                f"action={self.action!r})")


class FullLinkedSystem:
    def __init__(self, seed=42):
        self.system = MembraneNervous(seed=seed)
        self.ring = PropulsionRing()
        self.ledger = Ledger()

    def calibrate(self):
        rng = random.Random(11)
        in_p = [noisy(self.system.patterns[k % 4], 0.15, rng)
                for k in range(100)]
        ood_p = [rand_field(128, rng) for _ in range(100)]
        return self.system.calibrate(in_p, ood_p)

    def sonify(self, samples, rate=8000, hold=40):
        """Map tick samples to a WAV in memory. Mapping only:
        each tick sample is held for `hold` frames. The WAV is
        a sonification of the probe's journey, not a recording."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            frames = b""
            for s in samples:
                v = max(-1.0, min(1.0, s))
                frames += struct.pack("<h", int(v * 32767)) * hold
            w.writeframes(frames)
        return buf.getvalue()

    def run(self, probe, f_hz=7.0, total_steps=2000, truth=None):
        """truth is for scoring only, never for deciding."""
        if self.system.tau is None:
            raise ValueError("calibrate the gate first")
        self.ledger = Ledger()
        sens = sensitivity(f_hz)
        self.ledger.append("frequency", {"f_hz": f_hz, "sensitivity": sens},
                           "alert")
        inj = CrystallizeInjection(self.system)
        res = inj.attempt(probe, f_hz, rng=random.Random(1234),
                          truth=truth)
        decision, response = res.decision, res.response
        self.ledger.append("decision",
                           {"decision": decision, "response": response,
                            "attempts": res.attempts,
                            "best_overlap": res.best_overlap},
                           "alert")
        drive = RESPONSE_TO_DRIVE[response] if decision == "accept" else 0
        self.ring.set_drive(drive)
        clock = HeartClock()
        start = self.ring.position
        samples = []
        for _ in range(total_steps):
            if clock.step():
                self.ring.tick_move()
                # probe-following sensor: phase at probe position
                i = int(math.floor(self.ring.position)) % self.ring.n
                phase = self.ring.phases[i]
                samples.append(math.cos(phase))
        displacement = self.ring.position - start
        sensor = self.ring.sensor()
        confirmed = sensor["k_est"] == drive
        action = "move" if (decision == "accept" and confirmed
                            and drive != 0) else "hold"
        self.ledger.append("propulsion",
                           {"drive": drive, "displacement": displacement,
                            "ticks": clock.ticks, "sensor": sensor,
                            "confirmed": confirmed}, action)
        wav = self.sonify(samples)
        self.ledger.append("listen",
                           {"samples": len(samples),
                            "wav_bytes": len(wav)}, "alert")
        return FullResult(
            decision=decision, response=response, drive=drive,
            displacement=displacement, heart_ticks=clock.ticks,
            sensor=sensor, confirmed=confirmed, action=action,
            sensitivity=sens, attempts=res.attempts,
            p1=res.p1, best_overlap=res.best_overlap,
            brier=res.brier, net=res.net,
            listen_samples=samples, wav_bytes=len(wav),
            ledger_ok=self.ledger.verify(),
            ledger_entries=len(self.ledger.entries))
