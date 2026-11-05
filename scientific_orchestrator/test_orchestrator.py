"""Stdlib unit/integration checks; scratch outputs stay within this package."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import unittest
from unittest.mock import patch

from scientific_orchestrator import Contract, execute, load_config, validate_config, verify
from scientific_orchestrator import adapters
from scientific_orchestrator.core import (
    _contract_for, canonical, digest, execution_seed, replay, source_lock,
)

PACKAGE = Path(__file__).resolve().parent


def fail_adapter(params, seed, parents):
    raise ValueError("deliberate failure")


def slow_adapter(params, seed, parents):
    time.sleep(1)
    return adapters.signal_generator(params, seed, parents)


def malformed_adapter(params, seed, parents):
    return {"values": [float("nan")]}


def memory_adapter(params, seed, parents):
    allocation = bytearray(256 * 1024 * 1024)
    return {"values": [len(allocation)]}


def cpu_adapter(params, seed, parents):
    while True:
        pass


def invalid_probability_adapter(params, seed, parents):
    data = adapters.legacy_chain(params, seed, parents)
    data["values"][0]["p1"] = 1.5
    return data


def boolean_probability_adapter(params, seed, parents):
    data = adapters.legacy_chain(params, seed, parents)
    data["values"][0]["p1"] = True
    return data


def invalid_record_adapter(params, seed, parents):
    data = adapters.legacy_chain(params, seed, parents)
    data["values"][0]["ledger_ok"] = "true"
    return data


def send_then_hang_worker(connection, node, seed, parents, limits):
    data = adapters.signal_generator(node["params"], seed, parents)
    connection.send({"status": "SUCCESS", "data": data,
                     "runtime": {"wall_seconds": 0.001, "cpu_seconds": 0.001,
                                 "peak_memory_kb": 1}})
    time.sleep(5)


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(PACKAGE / "smoke.json")
        self.work = PACKAGE / f".test-work-{os.getpid()}-{self._testMethodName}"
        self.work.mkdir()

    def tearDown(self):
        shutil.rmtree(self.work)

    def run_config(self, config=None, directory="run", extended=False):
        output = self.work / directory
        return execute(config or self.config, output, extended), output

    def test_valid_plan_and_contract(self):
        plan = validate_config(self.config)
        self.assertEqual(plan["node_seed_runs"], 6)
        self.assertEqual(plan["seeds"], [1, 2, 3])
        self.assertEqual(plan["cost_estimate"]["maximum_attempted_runs"], 6)
        self.assertEqual(plan["cost_estimate"]["declared_max_wall_seconds"], 20)
        self.assertEqual(plan["cost_estimate"]["declared_max_cpu_seconds"], 10)
        self.assertEqual(plan["cost_estimate"]["declared_max_memory_mb_per_process"], 256)
        self.assertFalse(plan["cost_estimate"]["measured"])
        self.assertEqual(Contract.from_dict(self.config["nodes"][0]["contract"]).shape, [64])
        self.assertEqual(adapters.TRANSFORMS, {})

    def test_strict_numeric_and_unknown_schema(self):
        for value in (True, float("nan"), float("inf"), -1, 1.1):
            with self.subTest(value=value):
                config = copy.deepcopy(self.config)
                config["nodes"][0]["params"]["missing_probability"] = value
                with self.assertRaises((ValueError, TypeError)):
                    validate_config(config)
        for value in (True, 0, -4):
            config = copy.deepcopy(self.config)
            config["nodes"][0]["params"]["sample_rate"] = value
            with self.assertRaises(ValueError):
                validate_config(config)
        config = copy.deepcopy(self.config)
        config["command"] = "arbitrary shell command"
        with self.assertRaises(ValueError):
            validate_config(config)
        config = copy.deepcopy(self.config)
        config["budgets"]["workers"] = 2
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_json_duplicate_and_nonfinite_rejected(self):
        path = self.work / "invalid.json"
        for content in ('{"version":1,"version":1}', '{"value":NaN}', '{"value":1e400}'):
            path.write_text(content)
            with self.assertRaises(ValueError):
                load_config(path)

    def test_disjoint_protocol_and_exact_edges(self):
        config = copy.deepcopy(self.config)
        config["protocol"]["heldout"] = [1]
        with self.assertRaises(ValueError):
            validate_config(config)
        for field, value in (("shape", [65]), ("units", "volts"),
                             ("sample_rate", 32), ("evidence_origin", "legacy")):
            config = copy.deepcopy(self.config)
            config["nodes"][1]["input_contract"][field] = value
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_malformed_contracts(self):
        contract = self.config["nodes"][0]["contract"]
        for field, value in (
                ("shape", []), ("shape", [128, 156]), ("shape", [True]),
                ("shape", [1.5]), ("shape", [float("nan")]),
                ("coordinates", []), ("coordinates", ["time", "time"]),
                ("coordinates", [False]), ("sample_rate", False),
                ("sample_rate", float("inf")), ("units", {}),
                ("normalization", ""), ("evidence_origin", "independently_preregistered"),
                ("data_type", "implicit_padding")):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(contract)
                changed[field] = value
                with self.assertRaises(ValueError):
                    Contract.from_dict(changed)
        changed = copy.deepcopy(contract)
        changed["unrecognized"] = 1
        with self.assertRaises(ValueError):
            Contract.from_dict(changed)
        changed = copy.deepcopy(contract)
        del changed["time"]
        with self.assertRaises(ValueError):
            Contract.from_dict(changed)

    def test_dimension_156_cannot_consume_128(self):
        self.config["nodes"][0]["params"]["samples"] = 128
        self.config["nodes"][0]["contract"]["shape"] = [128]
        self.config["nodes"][1]["input_contract"]["shape"] = [156]
        with self.assertRaisesRegex(ValueError, "incompatible parent contract"):
            validate_config(self.config)

    def test_cycles(self):
        contract = self.config["nodes"][0]["contract"]
        self.config["nodes"] = [
            {"id": "a", "adapter": "public_adapter", "parents": ["b"], "params": {},
             "contract": contract, "input_contract": contract},
            {"id": "b", "adapter": "public_adapter", "parents": ["a"], "params": {},
             "contract": contract, "input_contract": contract},
        ]
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_config(self.config)

    def test_heldout_forbidden_and_calibration_opt_in(self):
        self.config["protocol"]["run_split"] = "heldout"
        for extended in (False, True):
            with self.assertRaisesRegex(ValueError, "heldout execution is unavailable"):
                self.run_config(extended=extended)
        self.config["protocol"]["run_split"] = "calibration"
        with self.assertRaisesRegex(ValueError, "dev seeds"):
            self.run_config()
        result, output = self.run_config(extended=True)
        self.assertEqual({r["seed"] for r in result["runs"]}, {101})
        self.assertTrue(verify(output)["valid"])
        config = copy.deepcopy(self.config)
        config["protocol"]["run_split"] = "dev"
        config["budgets"]["wall_seconds"] = 31
        with self.assertRaisesRegex(ValueError, "smoke cap"):
            self.run_config(config, directory="cap")

    def test_heldout_identity_rejected_by_verify(self):
        result, output = self.run_config()
        identity = json.loads((output / "objects" / (result["identity_id"] + ".json")).read_text())
        identity["config"]["protocol"]["run_split"] = "heldout"
        identity["config_hash"] = digest(identity["config"])
        identity["dataset_hash"] = digest({"protocol": identity["config"]["protocol"],
                                           "nodes": identity["config"]["nodes"]})
        identity["extended"] = True
        result["identity_id"] = digest(identity)
        result["run_id"] = digest(identity)
        (output / "objects" / (result["identity_id"] + ".json")).write_bytes(canonical(identity))
        (output / "manifest.json").write_bytes(canonical(result))
        with self.assertRaisesRegex(ValueError, "heldout execution is unavailable"):
            verify(output)

    def test_cpu_budget_requires_integer_seconds(self):
        for value in (0.01, 0.5, 1.5, True):
            config = copy.deepcopy(self.config)
            config["budgets"]["cpu_seconds"] = value
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_determinism_resume_and_exports(self):
        first, out1 = self.run_config(directory="first")
        second, out2 = self.run_config(directory="second")
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["runs"], second["runs"])
        config_hash = digest(self.config)
        derived = set()
        for record in first["runs"]:
            expected = execution_seed(config_hash, record["node"], "dev", record["seed"])
            self.assertEqual(record["execution_seed"], expected)
            self.assertIn(record["seed"], (1, 2, 3))
            derived.add(expected)
        self.assertEqual(len(derived), 6)
        self.assertNotEqual(execution_seed(config_hash, "telemetry", "dev", 1),
                            execution_seed(config_hash, "telemetry", "calibration", 1))
        self.assertNotEqual(execution_seed(config_hash, "telemetry", "dev", 1),
                            execution_seed(digest({"another": "config"}), "telemetry", "dev", 1))
        self.assertEqual({r["status"] for r in first["runs"]}, {"SUCCESS"})
        self.assertTrue(verify(out1)["valid"])
        self.assertTrue(verify(out2)["valid"])
        self.assertEqual(execute(self.config, out1)["runs"], first["runs"])
        result = json.loads((out1 / "results.json").read_text())
        summary = result["signal_comparison"]
        self.assertEqual(summary["independent_seed_clusters"], 3)
        self.assertEqual(summary["counts"]["rms"]["tp"], 3)
        self.assertEqual(summary["ci95"], [-1, 1])
        self.assertFalse(summary["threshold_supported"])
        self.assertTrue((out1 / "results.csv").read_text().startswith("node,seed,adapter,"))
        page = (out1 / "results.html").read_text()
        self.assertIn("All implemented evidence is synthetic; legacy identifies source lineage.", page)
        self.assertNotIn("Synthetic and legacy origins are separate", page)
        changed = copy.deepcopy(self.config)
        changed["protocol"]["practical_threshold"] = 0.2
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            execute(changed, out1)

    def test_artifact_export_and_source_tampering(self):
        result, output = self.run_config()
        artifact = output / "objects" / (result["runs"][0]["artifact_id"] + ".json")
        original = artifact.read_bytes()
        artifact.write_bytes(original + b" ")
        with self.assertRaises(ValueError):
            verify(output)
        artifact.write_bytes(original)
        original_csv = (output / "results.csv").read_bytes()
        (output / "results.csv").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "export digest"):
            verify(output)
        (output / "results.csv").write_bytes(original_csv)
        with patch("scientific_orchestrator.core.source_lock", return_value={"other": "hash"}):
            with self.assertRaisesRegex(ValueError, "source identity"):
                verify(output)
        self.assertTrue(verify(output)["valid"])

    def test_seed_provenance_tampering(self):
        result, output = self.run_config()
        result["runs"][0]["seed"] = 999
        (output / "manifest.json").write_bytes(canonical(result))
        with self.assertRaisesRegex(ValueError, "unexpected"):
            verify(output)

    def test_derived_seed_tampering(self):
        result, output = self.run_config()
        result["runs"][0]["execution_seed"] ^= 1
        (output / "manifest.json").write_bytes(canonical(result))
        with self.assertRaisesRegex(ValueError, "derived execution seed mismatch"):
            verify(output)

    def test_budget_lists_skipped_and_blocked(self):
        self.config["budgets"]["max_runs"] = 1
        self.assertEqual(validate_config(self.config)["cost_estimate"]["maximum_attempted_runs"], 1)
        result, output = self.run_config()
        self.assertEqual(len(result["runs"]), 6)
        self.assertEqual([r["status"] for r in result["runs"]],
                         ["SUCCESS", "SKIPPED", "SKIPPED", "BLOCKED", "SKIPPED", "BLOCKED"])
        self.assertTrue(verify(output)["valid"])
        self.assertFalse(json.loads((output / "results.json").read_text())[
            "signal_comparison"]["complete"])

    def test_runtime_clear_tamper_blocks_verify_and_resume(self):
        result, output = self.run_config()
        result["runtime"]["runs"] = []
        (output / "manifest.json").write_bytes(canonical(result))
        with self.assertRaisesRegex(ValueError, "budget accounting mismatch"):
            verify(output)
        with self.assertRaisesRegex(ValueError, "budget accounting mismatch"):
            execute(self.config, output)
        self.assertFalse((output / ".execution.lock").exists())

    def test_rehashed_accounting_validates_types_and_attempt_correspondence(self):
        mutations = {
            "negative_cpu": lambda a: a["runs"][0].update(cpu_seconds=-1),
            "negative_worker_wall": lambda a: a["runs"][0].update(wall_seconds=-1),
            "negative_peak": lambda a: a["runs"][0].update(peak_memory_kb=-1),
            "boolean_cpu": lambda a: a["runs"][0].update(cpu_seconds=True),
            "negative_total_cpu": lambda a: a.update(cpu_seconds_used=-1),
            "negative_cumulative_wall": lambda a: a.update(cumulative_wall_seconds=-1),
            "empty_runs": lambda a: a.update(runs=[], cpu_seconds_used=0, attempts=0),
            "wrong_execution_seed": lambda a: a["runs"][0].update(execution_seed=0),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                result, output = self.run_config(directory=name)
                account_path = output / "objects" / (result["accounting_id"] + ".json")
                accounting = json.loads(account_path.read_text())
                mutate(accounting)
                result["runtime"] = {key: value for key, value in accounting.items()
                                     if key not in ("kind", "run_id")}
                result["accounting_id"] = digest(accounting)
                (output / "objects" / (result["accounting_id"] + ".json")).write_bytes(
                    canonical(accounting))
                (output / "manifest.json").write_bytes(canonical(result))
                with self.assertRaises(ValueError):
                    verify(output)

    def test_orchestration_wall_is_persisted_and_debited_on_resume(self):
        from scientific_orchestrator import core
        self.config["budgets"]["wall_seconds"] = 0.1
        self.config["budgets"]["per_run_seconds"] = 0.05
        output = self.work / "interrupted"
        real_export, real_atomic = core._export, core._atomic

        def slow_export(*arguments):
            time.sleep(0.15)
            return real_export(*arguments)

        def interrupt_after_checkpoint(path, data):
            real_atomic(path, data)
            if path.name == "manifest.json":
                raise RuntimeError("checkpoint interruption")

        with patch.object(core, "_export", slow_export), patch.object(
                core, "_atomic", interrupt_after_checkpoint):
            with self.assertRaisesRegex(RuntimeError, "checkpoint interruption"):
                execute(self.config, output)
        checkpoint = json.loads((output / "manifest.json").read_text())
        previous_wall = checkpoint["runtime"]["cumulative_wall_seconds"]
        self.assertGreaterEqual(previous_wall, 0.15)
        self.assertEqual(checkpoint["runtime"]["runs"], [])
        self.assertEqual(checkpoint["runtime"]["attempts"], 0)
        self.assertTrue(verify(output, _allow_incomplete=True)["valid"])
        resumed = execute(self.config, output)
        self.assertFalse(any(record["attempted"] for record in resumed["runs"]))
        self.assertEqual({record["status"] for record in resumed["runs"]}, {"SKIPPED", "BLOCKED"})
        self.assertGreater(resumed["runtime"]["cumulative_wall_seconds"], previous_wall)
        self.assertTrue(verify(output)["valid"])

    def test_missing_adapter_blocked_and_replayable(self):
        self.config["nodes"] = [
            {"id": "<unavailable>", "adapter": "public_adapter", "parents": [],
             "params": {}, "contract": self.config["nodes"][0]["contract"]}]
        result, output = self.run_config()
        self.assertEqual({r["status"] for r in result["runs"]}, {"BLOCKED"})
        self.assertNotIn("<unavailable>", (output / "results.html").read_text())
        self.assertIn("&lt;unavailable&gt;", (output / "results.html").read_text())
        capsule = result["runs"][0]["capsule_id"]
        again = replay(output, capsule, self.work / "replay")
        self.assertEqual(again["runs"], result["runs"])

    def test_failures_timeouts_and_malformed_data(self):
        self.config["protocol"]["dev"] = [1]
        for function, status, directory in (
                (fail_adapter, "FAILED", "failure"),
                (slow_adapter, "TIMEOUT", "timeout"),
                (malformed_adapter, "FAILED", "malformed")):
            config = copy.deepcopy(self.config)
            config["budgets"]["per_run_seconds"] = 0.05 if status == "TIMEOUT" else 5
            with patch.dict(adapters.FUNCTIONS, {"signal_generator": function}):
                result, output = self.run_config(config, directory=directory)
            self.assertEqual(result["runs"][0]["status"], status)
            self.assertEqual(result["runs"][1]["status"], "BLOCKED")
            self.assertTrue(verify(output)["valid"])

    def test_worker_result_does_not_allow_unbounded_join(self):
        self.config["protocol"]["dev"] = [1]
        self.config["budgets"]["per_run_seconds"] = 0.05
        began = time.monotonic()
        with patch("scientific_orchestrator.core._worker", send_then_hang_worker):
            result, output = self.run_config()
        self.assertLess(time.monotonic() - began, 3)
        self.assertEqual(result["runs"][0]["status"], "TIMEOUT")
        self.assertEqual(result["runs"][1]["status"], "BLOCKED")
        self.assertTrue(verify(output)["valid"])
    def test_memory_limit_enforced(self):
        self.config["protocol"]["dev"] = [1]
        self.config["budgets"]["memory_mb"] = 64
        with patch.dict(adapters.FUNCTIONS, {"signal_generator": memory_adapter}):
            result, output = self.run_config()
        self.assertEqual(result["runs"][0]["status"], "BUDGET_EXCEEDED")
        self.assertIn("memory", result["runs"][0]["error"])
        self.assertTrue(verify(output)["valid"])

    def test_cpu_limit_enforced(self):
        self.config["protocol"]["dev"] = [1]
        self.config["budgets"]["cpu_seconds"] = 1
        with patch.dict(adapters.FUNCTIONS, {"signal_generator": cpu_adapter}):
            result, output = self.run_config()
        self.assertEqual(result["runs"][0]["status"], "BUDGET_EXCEEDED")
        self.assertEqual(result["runs"][1]["status"], "BLOCKED")
        self.assertTrue(verify(output)["valid"])

    def test_stress_controls_and_missing_failure(self):
        self.config["protocol"]["dev"] = [1]
        nodes = []
        for stress in adapters.STRESSES:
            generator, baseline = copy.deepcopy(self.config["nodes"])
            generator["id"] = stress
            generator["params"]["stress"] = stress
            generator["contract"]["noise"] = stress
            baseline["id"] = stress + "-baseline"
            baseline["parents"] = [stress]
            baseline["input_contract"] = copy.deepcopy(generator["contract"])
            nodes.extend((generator, baseline))
        self.config["nodes"] = nodes
        self.config["budgets"]["max_runs"] = 16
        result, output = self.run_config(extended=True)
        self.assertEqual({r["status"] for r in result["runs"]}, {"SUCCESS"})
        self.assertTrue(verify(output)["valid"])
        comparison = json.loads((output / "results.json").read_text())["signal_comparison"]
        self.assertEqual({condition["stress"] for condition in comparison["conditions"]},
                         set(adapters.STRESSES))
        self.assertEqual(len(comparison["conditions"]), 8)
        self.assertTrue(all(condition["complete"] for condition in comparison["conditions"]))
        self.assertTrue(all(condition["independent_seed_count"] == 1
                            for condition in comparison["conditions"]))
        self.assertTrue(all(condition["sign_flip_test"].startswith("NOT_COMPUTED")
                            for condition in comparison["conditions"]))
        scopes = {c["stress"]: c["stress_scope"] for c in comparison["conditions"]}
        self.assertEqual(scopes["local"], "time-local single-channel impulse")
        self.assertEqual(scopes["shared"], "time-shared single-channel offset")
        self.assertTrue(all(c["multichannel_validation"] == "NOT_IMPLEMENTED"
                            for c in comparison["conditions"]))
        data = json.loads((output / "objects" /
                          (result["runs"][3]["artifact_id"] + ".json")).read_text())["data"]
        self.assertFalse(data["event_reference"])
        config = load_config(PACKAGE / "smoke.json")
        config["protocol"]["dev"] = [1]
        config["nodes"][0]["params"]["stress"] = "missing"
        config["nodes"][0]["params"]["missing_probability"] = 1
        config["nodes"][0]["contract"]["noise"] = "missing"
        config["nodes"][1]["input_contract"]["noise"] = "missing"
        result, output = self.run_config(config, directory="all-missing")
        self.assertEqual(result["runs"][1]["status"], "FAILED")
        self.assertIn("all samples missing", result["runs"][1]["error"])
        self.assertTrue(verify(output)["valid"])
        comparison = json.loads((output / "results.json").read_text())["signal_comparison"]
        condition = comparison["conditions"][0]
        self.assertEqual(condition["stress"], "missing")
        self.assertFalse(condition["complete"])
        self.assertEqual(condition["failure_intervals"], {"rms": None, "maxabs": None})
        self.assertIsNone(condition["ci95"])
        self.assertEqual(condition["seed_outcomes"][0]["status"], "FAILED")

    def test_null_condition_independent_seed_intervals_and_source_lock(self):
        self.config["protocol"]["dev"] = [1, 2]
        clean_generator, clean_baseline = self.config["nodes"]
        null_generator = copy.deepcopy(clean_generator)
        null_generator["id"] = "null-generator"
        null_generator["params"]["stress"] = "null"
        null_generator["contract"]["noise"] = "null"
        null_baseline = copy.deepcopy(clean_baseline)
        null_baseline["id"] = "null-baseline"
        null_baseline["parents"] = ["null-generator"]
        null_baseline["input_contract"] = copy.deepcopy(null_generator["contract"])
        self.config["nodes"] += [null_generator, null_baseline]
        self.config["budgets"]["max_runs"] = 8
        result, output = self.run_config()
        self.assertTrue(verify(output)["valid"])
        self.assertEqual({record["seed"] for record in result["runs"]}, {1, 2})
        self.assertIn("benchmark_analysis.py", source_lock())
        comparison = json.loads((output / "results.json").read_text())["signal_comparison"]
        self.assertEqual(len(comparison["conditions"]), 2)
        null = next(c for c in comparison["conditions"] if c["stress"] == "null")
        self.assertEqual(null["status_counts"], {"SUCCESS": 2})
        self.assertEqual(null["independent_seed_count"], 2)
        self.assertTrue(all(not outcome["event_reference"] for outcome in null["seed_outcomes"]))
        for method in ("rms", "maxabs"):
            interval = null["failure_intervals"][method]
            self.assertEqual(interval["independent_unit"], "seed")
            self.assertEqual(interval["trials"], 2)
            self.assertEqual(interval["errors"], 0)
            self.assertGreater(interval["wilson_95"][1], 0)
            self.assertGreater(interval["zero_error_upper_95_one_sided"], 0)

    def test_legacy_adapter_and_frozen_sources(self):
        self.config["protocol"]["dev"] = [7]
        params = {"probe": "null", "noise_sigma": 0.1, "frequency": 7, "steps": 20}
        self.config["nodes"] = [{"id": "legacy", "adapter": "legacy_chain", "parents": [],
                                 "params": params, "contract": _contract_for("legacy_chain", params)}]
        root = PACKAGE.parent
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("*.py")}
        result, output = self.run_config()
        self.assertEqual(result["runs"][0]["status"], "SUCCESS")
        payload = json.loads((output / "objects" /
                              (result["runs"][0]["artifact_id"] + ".json")).read_text())
        data = payload["data"]
        self.assertIn("seed 11", data["evidence_caveat"])
        self.assertEqual(result["runs"][0]["evidence_origin"], "synthetic")
        self.assertEqual(payload["contract"]["evidence_origin"], "synthetic")
        self.assertEqual(data["evidence_origin"], "synthetic")
        self.assertIn("NOT_MEASURED", data["measurement_status"])
        invariant = data["calibration_invariants"]
        self.assertEqual(invariant["tau_before"], invariant["tau_after"])
        self.assertEqual(invariant["patterns_before"], 4)
        self.assertEqual(invariant["patterns_before"], invariant["patterns_after"])
        self.assertTrue(invariant["tau_and_patterns_unchanged"])
        telemetry = data["values"][0]
        self.assertEqual(telemetry["injection_cost"], telemetry["injection_attempts"] * 0.01)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in root.glob("*.py")})
        self.assertTrue(verify(output)["valid"])

    def test_baseline_only_and_legacy_examples(self):
        for name, runs in (("baseline", 2), ("legacy", 1)):
            config = load_config(PACKAGE / (name + ".json"))
            result, output = self.run_config(config, directory=name)
            self.assertEqual(len(result["runs"]), runs)
            self.assertEqual({r["status"] for r in result["runs"]}, {"SUCCESS"})
            self.assertTrue(verify(output)["valid"])

    def test_independent_component_removal_and_missed_events(self):
        values = [0.0, 1.0, 0.0, None]
        rms = adapters.rms_baseline(values, 0.2, True)
        maxabs = adapters.maxabs_baseline(values, 0.5, True)
        source = {"values": values, "event_reference": True, "missing_count": 1,
                  "stress": "clean"}
        both = adapters.signal_baseline({"rms_threshold": 0.2, "maxabs_threshold": 0.5},
                                        1, [source])
        self.assertEqual(both["rms"], rms["metric"])
        self.assertEqual(both["maxabs"], maxabs["metric"])
        with patch.object(adapters, "maxabs_baseline", side_effect=RuntimeError("removed")):
            self.assertEqual(adapters.rms_baseline(values, 0.2, True), rms)
        with patch.object(adapters, "rms_baseline", side_effect=RuntimeError("removed")):
            self.assertEqual(adapters.maxabs_baseline(values, 0.5, True), maxabs)
        for detector in (adapters.rms_baseline, adapters.maxabs_baseline):
            for values_bad, threshold_bad, truth_bad in (
                    ([True], 0.2, True), ([float("nan")], 0.2, True),
                    ([1.0], False, True), ([1.0], float("inf"), True),
                    ([1.0], 0.2, 1)):
                with self.assertRaises(ValueError):
                    detector(values_bad, threshold_bad, truth_bad)
            missed = detector(values, 10, True)
            self.assertEqual(missed["event_state"], "MISSED")
            self.assertEqual(missed["counts"]["fn"], 1)
            self.assertEqual(missed["counts"]["tn"], 0)
            self.assertEqual(missed["latency"]["status"], "NOT_IMPLEMENTED")
            self.assertEqual(missed["latency"]["missed_events"], 1)
            self.assertIsNone(missed["latency"]["seconds"])
            true_null = detector([0.0, 0.0], 0.2, False)
            self.assertEqual(true_null["event_state"], "TRUE_NULL")
            with self.assertRaisesRegex(ValueError, "all samples missing"):
                detector([None, None], 0.2, True)

    def test_malformed_probability_and_record_outputs(self):
        config = load_config(PACKAGE / "legacy.json")
        for name, function in (("probability", invalid_probability_adapter),
                               ("boolean", boolean_probability_adapter),
                               ("record", invalid_record_adapter)):
            with patch.dict(adapters.FUNCTIONS, {"legacy_chain": function}):
                result, output = self.run_config(config, directory=name)
            self.assertEqual(result["runs"][0]["status"], "FAILED")
            self.assertIn("ValueError", result["runs"][0]["error"])
            self.assertTrue(verify(output)["valid"])

    def test_dynamic_nested_package_source_locked(self):
        result, output = self.run_config()
        source = self.work / "nested_source.py"
        source.write_text("VERSION = 1\n")
        self.assertIn(str(source.relative_to(PACKAGE.parent)), source_lock())
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            verify(output)
        source.unlink()
        self.assertTrue(verify(output)["valid"])

    def test_public_schema_and_missing_dependency_blocked(self):
        config = load_config(PACKAGE / "public.json")
        config["nodes"][0]["params"]["source_directory"] = str((self.work / "missing").resolve())
        result, output = self.run_config(config)
        self.assertEqual(result["runs"][0]["status"], "BLOCKED")
        self.assertTrue(result["runs"][0]["attempted"])
        self.assertIn("FileNotFoundError", result["runs"][0]["error"])
        self.assertTrue(verify(output)["valid"])
        self.assertTrue(adapters.VERSIONS["oes32_residual"].startswith("1:fc0059"))
        for value in ([0] * 31, [0] * 33, [True] * 32, [float("nan")] * 32):
            bad = copy.deepcopy(config)
            bad["nodes"][0]["params"]["reference"] = value
            with self.assertRaises(ValueError):
                validate_config(bad)
        config["nodes"][0]["parents"] = ["any"]
        config["nodes"][0]["input_contract"] = copy.deepcopy(config["nodes"][0]["contract"])
        with self.assertRaisesRegex(ValueError, "cannot consume parents"):
            validate_config(config)

    def test_public_timeout_and_pin_mismatch(self):
        config = load_config(PACKAGE / "public.json")
        config["nodes"][0]["params"]["source_directory"] = str(self.work.resolve())
        with patch("public_residual_adapter.evaluate",
                   side_effect=subprocess.TimeoutExpired(["pinned-child"], 0.1)):
            result, output = self.run_config(config, directory="timeout")
        self.assertEqual(result["runs"][0]["status"], "TIMEOUT")
        self.assertTrue(verify(output)["valid"])
        from public_residual_adapter import FILES
        for filename, _ in FILES.values():
            (self.work / filename).write_text("untrusted mismatching fixture")
        result, output = self.run_config(config, directory="mismatch")
        self.assertEqual(result["runs"][0]["status"], "FAILED")
        self.assertIn("pinned upstream file mismatch", result["runs"][0]["error"])
        self.assertTrue(verify(output)["valid"])

    def test_public_genuine_prepared_integration(self):
        directory = os.environ.get("OES32_PREPARED")
        if not directory:
            self.skipTest("genuine integration requires explicitly prepared OES32_PREPARED directory")
        from public_residual_adapter import inspect_prepared
        provenance = inspect_prepared(directory)
        for delta in (0, 0.25, 0.5):
            config = load_config(PACKAGE / "public.json")
            params = config["nodes"][0]["params"]
            params["source_directory"] = str(Path(directory).resolve())
            params["observed"] = [delta] + [0] * 31
            result, output = self.run_config(config, directory=str(delta))
            self.assertEqual(result["runs"][0]["status"], "SUCCESS")
            self.assertEqual(result["runs"][0]["criterion_passed"], delta <= 0.25)
            self.assertTrue(verify(output)["valid"])
            payload = json.loads((output / "objects" /
                                  (result["runs"][0]["artifact_id"] + ".json")).read_text())
            data = payload["data"]
            self.assertEqual(data["source"], provenance)
            self.assertEqual(data["values"], [delta] + [0] * 31)
            self.assertEqual(data["result"]["failed"], delta > 0.25)
            runtime = result["runtime"]["runs"][0]
            self.assertGreater(runtime["child_cpu_seconds"], 0)
            self.assertGreater(runtime["peak_child_memory_kb"], 0)
            self.assertAlmostEqual(runtime["cpu_seconds"],
                                   runtime["self_cpu_seconds"] + runtime["child_cpu_seconds"])


if __name__ == "__main__":
    unittest.main()
