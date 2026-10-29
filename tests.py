"""Tests for full-linked-system v0.1.0.
Run: python3 -m unittest tests -v
"""
import random
import unittest

from chain import FullLinkedSystem, RESPONSE_TO_DRIVE
from experiments import exp_lattice_battery
from human import sensitivity
from ledger import Ledger
from nervous import rand_field


def calibrated():
    s = FullLinkedSystem(seed=42)
    s.calibrate()
    return s


class TestFullLinked(unittest.TestCase):
    def test_frequency_sensitivity(self):
        self.assertAlmostEqual(sensitivity(7.0), 1.0)
        self.assertLess(sensitivity(0.25), 0.001)
        self.assertLess(sensitivity(10.0), 0.20)

    def test_clean_pain_7hz_prereg_f1(self):
        s = calibrated()
        r = s.run(s.system.patterns[0], f_hz=7.0)
        self.assertEqual((r.decision, r.response), ("accept", "withdraw"))
        self.assertEqual(r.drive, 1)
        self.assertGreater(r.displacement, 15)
        self.assertEqual(r.sensor["k_est"], 1)
        self.assertEqual(r.action, "move")
        self.assertTrue(r.ledger_ok)

    def test_clean_pain_off_frequency_prereg_f2(self):
        s = calibrated()
        r = s.run(s.system.patterns[0], f_hz=0.25)
        self.assertEqual(r.decision, "reject")
        self.assertEqual(r.attempts, 20)
        self.assertEqual(r.displacement, 0.0)
        self.assertEqual(r.action, "hold")

    def test_random_refused_prereg_f3(self):
        s = calibrated()
        r = s.run(rand_field(128, random.Random(7)), f_hz=7.0)
        self.assertEqual(r.decision, "reject")
        self.assertEqual(r.displacement, 0.0)

    def test_grasp_reverse(self):
        s = calibrated()
        r = s.run(s.system.patterns[1], f_hz=7.0)
        self.assertEqual((r.decision, r.response), ("accept", "grasp"))
        self.assertEqual(r.drive, -1)
        self.assertLess(r.displacement, -15)

    def test_routing_and_lesion_prereg_f5(self):
        s = calibrated()
        pain = s.system.seed_ids[0]
        self.assertLess(s.system.reflex_time(pain),
                        s.system.central_time(pain))
        self.assertEqual(s.system.lesion_reflex_time(pain), float("inf"))

    def test_no_move_on_non_tick(self):
        from ring import HeartClock, PropulsionRing
        clock = HeartClock()
        ring = PropulsionRing()
        ring.set_drive(1)
        self.assertFalse(clock.step())
        self.assertEqual(ring.position, 0.0)

    def test_listen_prereg_f8(self):
        s = calibrated()
        r = s.run(s.system.patterns[0], f_hz=7.0)
        self.assertEqual(len(r.listen_samples), 200)
        self.assertGreater(r.wav_bytes, 10000)

    def test_ledger_rejects_bad_action(self):
        led = Ledger()
        with self.assertRaises(ValueError):
            led.append("x", {}, "fire")
        led.append("a", {}, "move")
        self.assertTrue(led.verify())

    def test_lattice_battery_prereg_f6(self):
        self.assertTrue(exp_lattice_battery(reps=5)["bar_F6"]["pass"])

    def test_tau_and_patterns_unchanged_prereg_f7(self):
        s = calibrated()
        tau = s.system.tau
        s.run(s.system.patterns[0], f_hz=7.0)
        self.assertEqual(s.system.tau, tau)
        self.assertEqual(len(s.system.patterns), 4)

    def test_drive_map_fail_safe(self):
        self.assertEqual(RESPONSE_TO_DRIVE["balance"], 0)
        self.assertEqual(RESPONSE_TO_DRIVE["cool-alert"], 0)


if __name__ == "__main__":
    unittest.main()
