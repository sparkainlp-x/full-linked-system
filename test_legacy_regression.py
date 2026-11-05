"""Additional frozen historical regressions; no legacy refactoring."""
import hashlib
import json
from pathlib import Path
import unittest

from experiments import exp_chain, exp_lattice_battery
from nervous import MembraneNervous
from lattice import build_pattern


ROOT = Path(__file__).resolve().parent


class LegacyRegression(unittest.TestCase):
    def test_archived_negative_and_dimension_separation(self):
        historical = json.loads((ROOT / "results.json").read_text())
        self.assertLess(historical["exp_chain"]["noisy_sigma_0_30"]["net_mean"], 0)
        self.assertLess(historical["exp_lattice_battery"]["row_slip"], 0.10)
        self.assertEqual(len(MembraneNervous(seed=42).patterns[0]), 128)
        self.assertEqual(len(build_pattern()), 156)

    def test_full_battery_preserves_negative_rescue_payoff(self):
        before = hashlib.sha256((ROOT / "results.json").read_bytes()).hexdigest()
        result = exp_chain()
        self.assertEqual(result["noisy_sigma_0_30"]["stock"], 19)
        self.assertEqual(result["noisy_sigma_0_30"]["injected"], 21)
        self.assertAlmostEqual(result["noisy_sigma_0_30"]["net_mean"], -0.277, places=3)
        self.assertTrue(result["tau_unchanged"])
        self.assertEqual(before, hashlib.sha256((ROOT / "results.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
