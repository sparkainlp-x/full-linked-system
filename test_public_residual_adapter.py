import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from public_residual_adapter import evaluate, prepare, strict_json, validate_request


def request(delta=0.25):
    return {"reference": [0] * 32, "observed": [delta] + [0] * 31, "tolerance": 0.25}


def response(delta=0.25):
    return {"component_residuals": [delta] + [0] * 31, "aggregate_residual": delta,
            "tolerance": 0.25, "passed": delta <= 0.25, "failed": delta > 0.25}


class PublicResidualTests(unittest.TestCase):
    def test_missing_dependency_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                evaluate(request(), directory)

    def test_preparation_is_never_implicit(self):
        with self.assertRaises(ValueError):
            prepare("/tmp/not-prepared")

    def test_malformed_requests_and_overflow(self):
        for value in [math.nan, math.inf, True, "1", -math.inf]:
            data = request()
            data["observed"][0] = value
            with self.assertRaises(ValueError):
                validate_request(data)
        for count in (31, 33, 128, 156):
            data = request()
            data["observed"] = [0] * count
            with self.assertRaises(ValueError):
                validate_request(data)
        data = request()
        data["reference"][0], data["observed"][0] = -1e308, 1e308
        with self.assertRaises(ValueError):
            validate_request(data)
        with self.assertRaises(ValueError):
            strict_json('{"tolerance":0,"tolerance":1}')

    @patch("pathlib.Path.read_bytes", return_value=b"verified source")
    @patch("public_residual_adapter.hashlib.sha256")
    @patch("public_residual_adapter.inspect_prepared", return_value={})
    @patch("public_residual_adapter.subprocess.run")
    def test_subprocess_and_analytic_equality(self, run, inspect, sha, read):
        from public_residual_adapter import FILES
        sha.return_value.hexdigest.return_value = FILES["src/residual_reference.py"][1]
        run.return_value.stdout = json.dumps(response())
        self.assertTrue(evaluate(request(), "/tmp/source")["result"]["passed"])
        self.assertIs(run.call_args.kwargs["shell"], False)
        self.assertEqual(run.call_args.kwargs["timeout"], 5)
        run.return_value.stdout = json.dumps(response(0.5))
        self.assertTrue(evaluate(request(0.5), "/tmp/source")["result"]["failed"])

    @patch("pathlib.Path.read_bytes", return_value=b"verified source")
    @patch("public_residual_adapter.hashlib.sha256")
    @patch("public_residual_adapter.inspect_prepared", return_value={})
    @patch("public_residual_adapter.subprocess.run")
    def test_timeout_and_invalid_output_never_pass(self, run, inspect, sha, read):
        from public_residual_adapter import FILES
        sha.return_value.hexdigest.return_value = FILES["src/residual_reference.py"][1]
        run.side_effect = subprocess.TimeoutExpired("trusted interpreter", 0.01)
        with self.assertRaises(subprocess.TimeoutExpired):
            evaluate(request(), "/tmp/source", 0.01)
        run.side_effect = None
        for bad in ["{}", '{"aggregate_residual":NaN}', json.dumps(response(0.5))]:
            run.return_value.stdout = bad
            with self.assertRaises(ValueError):
                evaluate(request(), "/tmp/source")

    def test_source_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "residual_reference.py").write_text("print('mock')")
            with self.assertRaises(ValueError):
                evaluate(request(), directory)

    @patch("public_residual_adapter.inspect_prepared", return_value={})
    @patch("pathlib.Path.read_bytes", return_value=b"changed after inspection")
    def test_source_changed_between_inspection_and_execution(self, read, inspect):
        with self.assertRaises(ValueError):
            evaluate(request(), "/tmp/source")


if __name__ == "__main__":
    unittest.main()
