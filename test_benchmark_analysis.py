import math
import unittest

from benchmark_analysis import failure_interval, holm_adjust, paired_comparison


class AnalysisTests(unittest.TestCase):
    def test_zero_errors_is_not_zero_probability(self):
        result = failure_interval(0, 10)
        self.assertGreater(result["wilson_95"][1], 0)
        self.assertAlmostEqual(result["zero_error_upper_95_one_sided"], 1 - 0.05 ** 0.1)

    def test_wilson_reference(self):
        self.assertAlmostEqual(failure_interval(5, 10)["wilson_95"][0], 0.23659309)
        self.assertAlmostEqual(failure_interval(5, 10)["wilson_95"][1], 0.76340691)

    def test_paired_exact_reference(self):
        baseline = dict.fromkeys(range(4), 0.0)
        self.assertEqual(paired_comparison(baseline, baseline, 0.1)["two_sided_sign_flip_p"], 1)
        treatment = dict.fromkeys(range(4), 1.0)
        result = paired_comparison(baseline, treatment, 0.1)
        self.assertEqual(result["two_sided_sign_flip_p"], 0.125)
        self.assertEqual(result["n_pairs"], 4)

    def test_pairing_and_independence_required(self):
        for args in [({}, {}, 0), ({1: 1}, {2: 1}, 0),
                     ({1: 1}, {1: 2}, -1), ({1: 1}, {1: math.inf}, 0)]:
            with self.assertRaises(ValueError):
                paired_comparison(*args)
        with self.assertRaises(ValueError):
            paired_comparison({1: 1}, {1: 2}, 0, "frame")

    def test_holm_reference_and_malformed(self):
        self.assertEqual(holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03}),
                         {"a": 0.03, "c": 0.06, "b": 0.06})
        for p in [math.nan, math.inf, -0.1, 1.1, True]:
            with self.assertRaises(ValueError):
                holm_adjust({"x": p})
        for errors, trials in [(True, 1), (1, 0), (2, 1), (-1, 3)]:
            with self.assertRaises(ValueError):
                failure_interval(errors, trials)


if __name__ == "__main__":
    unittest.main()
