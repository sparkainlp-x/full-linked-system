"""Strict versioned plans and isolated, serial, resource-limited local execution."""

import csv
from dataclasses import asdict, dataclass
import hashlib
import html
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import sys
import time

from benchmark_analysis import failure_interval

from . import adapters

ROOT = Path(__file__).resolve().parent.parent
SMOKE_CAPS = {"max_runs": 12, "workers": 1, "wall_seconds": 30,
              "cpu_seconds": 20, "memory_mb": 256, "per_run_seconds": 10}
EXTENDED_CAPS = {"max_runs": 128, "workers": 1, "wall_seconds": 300,
                 "cpu_seconds": 240, "memory_mb": 1024, "per_run_seconds": 60}
STATUSES = {"SUCCESS", "FAILED", "TIMEOUT", "BUDGET_EXCEEDED", "BLOCKED", "SKIPPED"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _fields(value, required, optional=(), label="object"):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(f"{label}: missing {sorted(missing)}, unknown {sorted(unknown)}")


def _number(value, label, low=0, high=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number, not bool")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or value < low or (high is not None and value > high):
        raise ValueError(f"{label} outside finite bounds [{low}, {high}]")
    if integer and not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")


def _text(value, label, choices=None):
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError(f"{label} must be a nonempty string of at most 200 characters")
    if choices is not None and value not in choices:
        raise ValueError(f"{label} must be one of {choices}")


@dataclass(frozen=True)
class Contract:
    """Exact contracts: no shape coercion, padding, truncation, or unit conversion.

    ``noise`` describes the model, not a numerical bound. Missing samples are
    explicit nulls only under ``float64_nullable``. Coordinates name each axis
    (or the named telemetry vector components).
    """

    data_type: str
    shape: list
    units: str
    coordinates: list
    sample_rate: object
    normalization: str
    time: str
    noise: str
    evidence_origin: str

    @classmethod
    def from_dict(cls, value):
        _fields(value, cls.__dataclass_fields__, label="contract")
        _text(value["data_type"], "data_type", ("float64", "float64_nullable", "record"))
        if not isinstance(value["shape"], list) or len(value["shape"]) != 1:
            raise ValueError("only explicit one-dimensional shapes are supported")
        _number(value["shape"][0], "shape", 1, 4096, integer=True)
        if not isinstance(value["coordinates"], list) or not value["coordinates"]:
            raise ValueError("coordinates must be a nonempty list")
        for coordinate in value["coordinates"]:
            _text(coordinate, "coordinate")
        if len(set(value["coordinates"])) != len(value["coordinates"]):
            raise ValueError("coordinates must be unique")
        for key in ("units", "normalization", "time", "noise"):
            _text(value[key], key)
        if value["sample_rate"] is not None:
            _number(value["sample_rate"], "sample_rate", 0.001, 1000000)
        _text(value["evidence_origin"], "evidence_origin", ("synthetic", "public"))
        return cls(**value)


def load_config(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    with Path(path).open("rb") as stream:
        raw = stream.read(1000001)
    if len(raw) > 1000000:
        raise ValueError("configuration exceeds 1 MB")
    config = json.loads(raw, object_pairs_hook=pairs,
                        parse_constant=lambda x: (_ for _ in ()).throw(
                            ValueError(f"nonfinite JSON constant {x}")))
    validate_config(config)
    return config


def _contract_for(adapter, params):
    if adapter == "signal_generator":
        return {"data_type": "float64_nullable", "shape": [params["samples"]],
                "units": "amplitude", "coordinates": ["time"],
                "sample_rate": params["sample_rate"], "normalization": "none",
                "time": "seconds from zero", "noise": params["stress"],
                "evidence_origin": "synthetic"}
    if adapter == "signal_baseline":
        return {"data_type": "float64", "shape": [2], "units": "amplitude",
                "coordinates": ["rms", "maxabs"], "sample_rate": None,
                "normalization": "none", "time": "summary", "noise": "inherited",
                "evidence_origin": "synthetic"}
    if adapter == "legacy_chain":
        return {"data_type": "record", "shape": [1], "units": "dimensionless",
                "coordinates": ["run"], "sample_rate": None,
                "normalization": "legacy", "time": "ticks", "noise": "legacy",
                "evidence_origin": "synthetic"}
    if adapter == "oes32_residual":
        return {"data_type": "float64", "shape": [32], "units": "dimensionless",
                "coordinates": ["component index"], "sample_rate": None,
                "normalization": "none", "time": "static", "noise": "deterministic",
                "evidence_origin": "synthetic"}
    return None


def validate_config(config):
    """Validate schema/DAG without execution; return a topologically ordered plan.

    Budget smoke/extended selection is enforced by execute(), not by this function.
    A run means one node-seed attempt (including generators), not one seed.
    """
    canonical(config)  # Also rejects nonfinite nested values.
    _fields(config, ("version", "protocol", "budgets", "nodes"), label="config")
    if type(config["version"]) is not int or config["version"] != 1:
        raise ValueError("version must be integer 1")
    p = config["protocol"]
    _fields(p, ("dev", "calibration", "heldout", "primary_metric",
                "practical_threshold", "baseline", "stopping", "interpretation",
                "run_split"), label="protocol")
    seen = set()
    for split in ("dev", "calibration", "heldout"):
        seeds = p[split]
        if not isinstance(seeds, list) or not seeds or len(seeds) > 128:
            raise ValueError(f"{split} must contain 1..128 seeds")
        for seed in seeds:
            _number(seed, "seed", 0, 2**32 - 1, integer=True)
            if seed in seen:
                raise ValueError("dev/calibration/heldout seed lists must be disjoint and unique")
            seen.add(seed)
    _text(p["primary_metric"], "primary_metric", ("paired_error_difference",))
    _number(p["practical_threshold"], "practical_threshold", 0, 1)
    _text(p["baseline"], "baseline", ("rms",))
    _text(p["stopping"], "stopping", ("fixed_budget",))
    _text(p["interpretation"], "interpretation", ("exploratory",))
    _text(p["run_split"], "run_split", ("dev", "calibration", "heldout"))
    if p["run_split"] == "heldout":
        raise ValueError("heldout execution is unavailable: no locked selection/use accounting")
    budgets = config["budgets"]
    _fields(budgets, SMOKE_CAPS, label="budgets")
    for key, cap in EXTENDED_CAPS.items():
        integral = key in ("max_runs", "workers", "memory_mb", "cpu_seconds")
        _number(budgets[key], key, 1 if integral else 0.01, cap, integer=integral)
    if budgets["workers"] != 1:
        raise ValueError("this bounded implementation supports workers=1 only")
    if budgets["per_run_seconds"] > budgets["wall_seconds"]:
        raise ValueError("per_run_seconds cannot exceed wall_seconds")
    nodes = config["nodes"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 64:
        raise ValueError("nodes must contain 1..64 nodes")
    by_id = {}
    for node in nodes:
        _fields(node, ("id", "adapter", "parents", "contract", "params"),
                ("input_contract",), label="node")
        _text(node["id"], "node id")
        if node["id"] in by_id:
            raise ValueError("duplicate node id")
        by_id[node["id"]] = node
        _text(node["adapter"], "adapter", tuple(adapters.VERSIONS))
        if not isinstance(node["parents"], list) or len(node["parents"]) > 1:
            raise ValueError("adapters support zero or one parent")
        for parent in node["parents"]:
            _text(parent, "parent id")
        Contract.from_dict(node["contract"])
        name, params = node["adapter"], node["params"]
        if name == "signal_generator":
            _fields(params, ("samples", "sample_rate", "amplitude", "noise_sigma",
                             "stress", "missing_probability"), label=name)
            _number(params["samples"], "samples", 8, 4096, integer=True)
            _number(params["sample_rate"], "sample_rate", 0.001, 1000000)
            _number(params["amplitude"], "amplitude", 0, 100)
            _number(params["noise_sigma"], "noise_sigma", 0, 100)
            _number(params["missing_probability"], "missing_probability", 0, 1)
            _text(params["stress"], "stress", adapters.STRESSES)
        elif name == "signal_baseline":
            _fields(params, ("rms_threshold", "maxabs_threshold"), label=name)
            for key in params:
                _number(params[key], key, 0, 1000)
        elif name == "legacy_chain":
            _fields(params, ("probe", "noise_sigma", "frequency", "steps"), label=name)
            _text(params["probe"], "probe", ("pulse", "null"))
            _number(params["noise_sigma"], "noise_sigma", 0, 10)
            _number(params["frequency"], "frequency", 0.001, 1000)
            _number(params["steps"], "steps", 1, 2000, integer=True)
        elif name == "oes32_residual":
            from public_residual_adapter import validate_request
            _fields(params, ("source_directory", "reference", "observed", "tolerance"), label=name)
            _text(params["source_directory"], "source_directory")
            if not Path(params["source_directory"]).is_absolute():
                raise ValueError("source_directory must be an explicit absolute path")
            validate_request({key: params[key] for key in ("reference", "observed", "tolerance")})
            for key in ("reference", "observed"):
                for value in params[key]:
                    _number(value, key, -1e100, 1e100)
            _number(params["tolerance"], "tolerance", 0, 1e100)
        else:
            _fields(params, (), label="unimplemented adapter params")
        expected = _contract_for(name, params)
        if expected is not None and node["contract"] != expected:
            raise ValueError(f"{node['id']}: adapter output contract mismatch")
        if name == "signal_baseline" and len(node["parents"]) != 1:
            raise ValueError("signal_baseline requires one signal_generator parent")
        if name in ("signal_generator", "legacy_chain", "oes32_residual") and node["parents"]:
            raise ValueError(f"{name} has no input contract and cannot consume parents")
        if node["parents"]:
            if "input_contract" not in node:
                raise ValueError("parent edge requires explicit input_contract")
            Contract.from_dict(node["input_contract"])
        elif "input_contract" in node:
            raise ValueError("input_contract without parents")
    ordered, visiting, visited = [], set(), set()

    def visit(key):
        if key not in by_id:
            raise ValueError(f"unknown parent: {key}")
        if key in visiting:
            raise ValueError("DAG cycle")
        if key in visited:
            return
        visiting.add(key)
        node = by_id[key]
        for parent in node["parents"]:
            visit(parent)
            source = by_id[parent]
            if source["contract"] != node["input_contract"]:
                raise ValueError(f"incompatible parent contract for {key}")
            if node["adapter"] == "signal_baseline" and source["adapter"] != "signal_generator":
                raise ValueError("signal_baseline consumes only signal_generator data")
        visiting.remove(key)
        visited.add(key)
        ordered.append(node)

    for key in by_id:
        visit(key)
    if len(ordered) * len(p[p["run_split"]]) > EXTENDED_CAPS["max_runs"]:
        raise ValueError("planned node-seed records exceed hard cap 128")
    return {"version": 1, "nodes": ordered, "seeds": list(p[p["run_split"]]),
            "node_seed_runs": len(ordered) * len(p[p["run_split"]]),
            "cost_estimate": {
                "planned_runs": len(ordered) * len(p[p["run_split"]]),
                "maximum_attempted_runs": min(budgets["max_runs"],
                                              len(ordered) * len(p[p["run_split"]])),
                "declared_max_wall_seconds": budgets["wall_seconds"],
                "declared_max_cpu_seconds": budgets["cpu_seconds"],
                "declared_max_memory_mb_per_process": budgets["memory_mb"],
                "declared_max_per_run_seconds": budgets["per_run_seconds"],
                "workers": budgets["workers"], "measured": False,
                "basis": "declared configuration ceilings, not measured or predicted costs",
                "memory_scope": "per-process address space; no aggregate parent/child RSS bound",
            },
            "coupling": "none unless an explicit compatible parent edge is supplied",
            "interpretation": "exploratory, not independently preregistered"}


def source_lock():
    """Hash all root Python sources and recursively all package Python sources."""
    paths = sorted(set(ROOT.glob("*.py")) |
                   set((ROOT / "scientific_orchestrator").rglob("*.py")))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def dependency_lock():
    return {"dependencies": "stdlib only", "python": sys.version,
            "implementation": platform.python_implementation(), "platform": sys.platform,
            "adapter_versions": adapters.VERSIONS}


def public_source_pin():
    from public_residual_adapter import FILES, REVISION, UPSTREAM, VERSION
    return {"repository": UPSTREAM, "revision": REVISION, "adapter_version": VERSION,
            "license": "AGPL-3.0-only",
            "file_sha256": {target: sha for target, sha in FILES.values()}}


def execution_seed(config_hash, node_id, partition, independent_seed):
    """Stable node/experiment RNG seed; the original seed remains the paired unit."""
    material = {"config_hash": config_hash, "node": node_id, "partition": partition,
                "independent_seed": independent_seed, "derivation": "sha256-node-partition-v1"}
    return int.from_bytes(hashlib.sha256(canonical(material)).digest()[:8], "big")


def _boolean(value, label):
    if type(value) is not bool:
        raise ValueError(f"{label} must be boolean")


def _validate_adapter_data(node, data):
    name, contract = node["adapter"], node["contract"]
    fields = {
        "signal_generator": ("values", "event_reference", "reference_window_seconds",
                             "missing_count", "stress", "reference_kind", "stress_scope",
                             "multichannel_validation"),
        "signal_baseline": ("values", "rms", "maxabs", "event_reference", "rms_event",
                            "maxabs_event", "counts", "event_states", "latency",
                            "coupling_benefit", "observed_samples", "missing_count", "stress"),
        "legacy_chain": ("values", "evidence_caveat", "evidence_origin", "source_lineage",
                         "measurement_status", "latency", "calibration_invariants", "cost_caveat"),
        "oes32_residual": ("values", "result", "source", "evidence_origin", "execution_status",
                          "interpretation", "limitations"),
    }
    _fields(data, fields[name], label="adapter data")
    values = data["values"]
    if not isinstance(values, list) or len(values) != contract["shape"][0]:
        raise ValueError("adapter returned incompatible shape")
    if contract["data_type"] != "record":
        for value in values:
            if value is None and contract["data_type"] == "float64_nullable":
                continue
            _number(value, "adapter value", -2e100, 2e100)
    if name == "signal_generator":
        _boolean(data["event_reference"], "event reference")
        _number(data["missing_count"], "missing_count", 0, len(values), integer=True)
        if data["missing_count"] != values.count(None):
            raise ValueError("missing sample count mismatch")
        if data["stress"] != node["params"]["stress"] or (
                data["event_reference"] != (data["stress"] != "null")):
            raise ValueError("stress/reference mismatch")
        window = data["reference_window_seconds"]
        if not isinstance(window, list) or len(window) != 2:
            raise ValueError("reference window must have two endpoints")
        for value in window:
            _number(value, "reference time", 0, len(values) / node["params"]["sample_rate"])
        if window[0] >= window[1]:
            raise ValueError("reference window must be ordered")
        for field in ("reference_kind", "stress_scope"):
            _text(data[field], field)
        _text(data["multichannel_validation"], "multichannel_validation", ("NOT_IMPLEMENTED",))
    elif name == "signal_baseline":
        _boolean(data["event_reference"], "event reference")
        _number(data["observed_samples"], "observed_samples", 1, 4096, integer=True)
        _number(data["missing_count"], "missing_count", 0, 4096, integer=True)
        if data["observed_samples"] + data["missing_count"] != node["input_contract"]["shape"][0]:
            raise ValueError("observed/missing sample count mismatch")
        for field in ("counts", "event_states", "latency"):
            _fields(data[field], ("rms", "maxabs"), label=field)
        for i, method in enumerate(("rms", "maxabs")):
            _number(data[method], method, 0, 1e100)
            _boolean(data[method + "_event"], method + "_event")
            if data[method] != values[i]:
                raise ValueError("telemetry metric/value mismatch")
            count = data["counts"][method]
            _fields(count, ("tp", "tn", "fp", "fn", "errors", "trials"), label="counts")
            for value in count.values():
                _number(value, "count", 0, 1, integer=True)
            expected = adapters._detection_report(data[method], node["params"][method + "_threshold"],
                                                  data["event_reference"])
            if count != expected["counts"] or data[method + "_event"] != expected["event"] or (
                    data["event_states"][method] != expected["event_state"]):
                raise ValueError("event presence/count mismatch")
            latency = data["latency"][method]
            _fields(latency, expected["latency"], label="latency")
            _number(latency["missed_events"], "missed_events", 0, 1, integer=True)
            if latency != expected["latency"]:
                raise ValueError("unsupported or inconsistent latency metadata")
        _text(data["stress"], "stress", adapters.STRESSES)
        _text(data["coupling_benefit"], "coupling_benefit")
    elif name == "oes32_residual":
        result = data["result"]
        _fields(result, ("component_residuals", "aggregate_residual", "tolerance", "passed", "failed"),
                label="pinned result")
        _boolean(result["passed"], "criterion passed")
        _boolean(result["failed"], "criterion failed")
        _number(result["aggregate_residual"], "aggregate_residual", 0, 2e100)
        _number(result["tolerance"], "tolerance", 0, 1e100)
        expected = [abs(y - x) for x, y in zip(node["params"]["reference"], node["params"]["observed"])]
        components = result["component_residuals"]
        if not isinstance(components, list) or len(components) != 32:
            raise ValueError("pinned result must contain exactly 32 components")
        for value in components:
            _number(value, "residual component", 0, 2e100)
        if components != values or values != expected or (
                result["aggregate_residual"] != max(expected)) or (
                result["tolerance"] != node["params"]["tolerance"]):
            raise ValueError("pinned result disagrees with analytic residual reference")
        passed = max(expected) <= result["tolerance"]
        if result["passed"] != passed or result["failed"] == passed:
            raise ValueError("pinned residual criterion mismatch")
        source = data["source"]
        _fields(source, ("repository", "revision", "license", "file_sha256", "trust"), label="source")
        pin = public_source_pin()
        if any(source[field] != pin[field] for field in ("repository", "revision", "license", "file_sha256")):
            raise ValueError("public source pin mismatch")
        _text(source["trust"], "source trust")
        _text(data["evidence_origin"], "evidence_origin", ("synthetic",))
        _text(data["execution_status"], "execution_status", ("passed",))
        for field in ("interpretation", "limitations"):
            _text(data[field], field)
    else:
        record = values[0]
        _fields(record, ("decision", "action", "response", "displacement", "p1", "brier",
                         "injection_attempts", "injection_cost", "ledger_ok"), label="legacy record")
        _text(record["decision"], "decision", ("accept", "reject"))
        _text(record["action"], "action", ("move", "hold"))
        if record["response"] is not None:
            _text(record["response"], "response", ("withdraw", "grasp", "balance", "cool-alert"))
        _number(record["displacement"], "synthetic displacement", -1e100, 1e100)
        _number(record["p1"], "legacy p1 probability", 0, 1)
        if record["brier"] is not None:
            _number(record["brier"], "brier", 0, 1)
        _number(record["injection_attempts"], "injection_attempts", 0, 20, integer=True)
        _number(record["injection_cost"], "injection_cost", 0, 0.2)
        if record["injection_cost"] != record["injection_attempts"] * 0.01:
            raise ValueError("injection cost mismatch")
        _boolean(record["ledger_ok"], "ledger_ok")
        if not record["ledger_ok"]:
            raise ValueError("legacy ledger failed verification")
        _text(data["evidence_origin"], "evidence_origin", ("synthetic",))
        for field in ("evidence_caveat", "source_lineage", "measurement_status", "cost_caveat"):
            _text(data[field], field)
        if not data["measurement_status"].startswith("NOT_MEASURED:"):
            raise ValueError("legacy adapter cannot claim measured evidence")
        if data["latency"] != {"status": "NOT_IMPLEMENTED", "seconds": None}:
            raise ValueError("legacy latency is not implemented")
        invariant = data["calibration_invariants"]
        _fields(invariant, ("tau_before", "tau_after", "patterns_before", "patterns_after",
                            "tau_and_patterns_unchanged"), label="calibration invariants")
        for field in ("tau_before", "tau_after"):
            _number(invariant[field], field, 0, 1)
        for field in ("patterns_before", "patterns_after"):
            _number(invariant[field], field, 1, 4096, integer=True)
        _boolean(invariant["tau_and_patterns_unchanged"], "tau_and_patterns_unchanged")
        if not invariant["tau_and_patterns_unchanged"] or (
                invariant["tau_before"] != invariant["tau_after"]) or (
                invariant["patterns_before"] != invariant["patterns_after"]):
            raise ValueError("legacy calibration invariants changed")


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + f".partial-{os.getpid()}")
    try:
        with staging.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        if staging.exists():
            staging.unlink()


def _object(output, value):
    identity = digest(value)
    path = output / "objects" / (identity + ".json")
    if path.exists():
        if path.read_bytes() != canonical(value):
            raise ValueError(f"existing content-addressed object is corrupt: {identity}")
    else:
        _atomic(path, canonical(value))
    return identity


def _read_object(output, identity):
    if not isinstance(identity, str) or len(identity) != 64 or any(
            c not in "0123456789abcdef" for c in identity):
        raise ValueError("invalid artifact identity")
    with (output / "objects" / (identity + ".json")).open("rb") as stream:
        raw = stream.read(4000001)
    if len(raw) > 4000000:
        raise ValueError("artifact exceeds bounded 4 MB object size")
    value = json.loads(raw)
    if digest(value) != identity or canonical(value) != raw:
        raise ValueError(f"artifact digest/canonical encoding mismatch: {identity}")
    return value


def _validate_accounting(output, manifest):
    accounting = _read_object(output, manifest["accounting_id"])
    _fields(accounting, ("kind", "run_id", "timestamp_utc", "runs", "cumulative_wall_seconds",
                         "cpu_seconds_used", "attempts"), label="budget accounting")
    if accounting["kind"] != "budget_accounting" or accounting["run_id"] != manifest["run_id"]:
        raise ValueError("budget accounting identity mismatch")
    runtime = {key: value for key, value in accounting.items() if key not in ("kind", "run_id")}
    if canonical(manifest["runtime"]) != canonical(runtime):
        raise ValueError("budget accounting mismatch: mutable runtime metadata")
    _text(accounting["timestamp_utc"], "accounting timestamp")
    _number(accounting["cumulative_wall_seconds"], "cumulative wall", 0)
    _number(accounting["cpu_seconds_used"], "cumulative CPU", 0)
    _number(accounting["attempts"], "accounted attempts", 0, 128, integer=True)
    if not isinstance(accounting["runs"], list) or len(accounting["runs"]) > 128:
        raise ValueError("accounted runs must be a bounded list")
    attempted = {(record["node"], record["seed"]): record for record in manifest["runs"]
                 if record["attempted"]}
    seen = set()
    cpu, wall = 0.0, 0.0
    for item in accounting["runs"]:
        _fields(item, ("node", "seed", "execution_seed", "wall_seconds", "cpu_seconds",
                       "peak_memory_kb"),
                ("self_cpu_seconds", "child_cpu_seconds", "peak_child_memory_kb", "memory_scope"),
                label="accounted worker")
        _text(item["node"], "accounted node")
        _number(item["seed"], "accounted seed", 0, 2**32 - 1, integer=True)
        _number(item["execution_seed"], "accounted execution seed", 0, 2**64 - 1, integer=True)
        key = (item["node"], item["seed"])
        if key in seen or key not in attempted:
            raise ValueError("budget accounting has duplicate or unattempted run")
        if item["execution_seed"] != attempted[key]["execution_seed"]:
            raise ValueError("budget accounting execution seed mismatch")
        seen.add(key)
        for field in ("cpu_seconds", "wall_seconds"):
            _number(item[field], field, 0)
        for field in ("peak_memory_kb", "peak_child_memory_kb"):
            if field in item and item[field] is not None:
                _number(item[field], field, 0, integer=True)
        if ("self_cpu_seconds" in item) != ("child_cpu_seconds" in item):
            raise ValueError("incomplete self/child CPU accounting")
        if "self_cpu_seconds" in item:
            for field in ("self_cpu_seconds", "child_cpu_seconds"):
                _number(item[field], field, 0)
            if not math.isclose(item["cpu_seconds"],
                                item["self_cpu_seconds"] + item["child_cpu_seconds"],
                                rel_tol=1e-12, abs_tol=1e-9):
                raise ValueError("self/child CPU total mismatch")
        if "memory_scope" in item:
            _text(item["memory_scope"], "memory_scope")
        cpu += item["cpu_seconds"]
        wall += item["wall_seconds"]
    if seen != set(attempted) or accounting["attempts"] != len(attempted):
        raise ValueError("budget accounting attempted-run correspondence mismatch")
    if not math.isclose(cpu, accounting["cpu_seconds_used"], rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("budget accounting cumulative CPU mismatch")
    if accounting["cumulative_wall_seconds"] + 1e-9 < wall:
        raise ValueError("cumulative wall accounting omits worker durations")
    return accounting


def _worker(connection, node, seed, parents, limits):
    import resource
    began = time.monotonic()
    try:
        os.setsid()
        memory = limits["memory_mb"] * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        cpu = max(1, math.ceil(limits["cpu_seconds"]))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        data = adapters.FUNCTIONS[node["adapter"]](node["params"], seed, parents)
        canonical(data)
        _validate_adapter_data(node, data)
        message = {"status": "SUCCESS", "data": data}
    except MemoryError:
        message = {"status": "BUDGET_EXCEEDED", "error": "memory limit exceeded"}
    except FileNotFoundError as error:
        message = {"status": "BLOCKED" if node["adapter"] == "oes32_residual" else "FAILED",
                   "error": f"{type(error).__name__}: {error}"}
    except subprocess.TimeoutExpired as error:
        message = {"status": "TIMEOUT", "error": f"{type(error).__name__}: {error}"}
    except BaseException as error:
        message = {"status": "FAILED", "error": f"{type(error).__name__}: {error}"}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    message["runtime"] = {"wall_seconds": time.monotonic() - began,
                          "cpu_seconds": usage.ru_utime + usage.ru_stime +
                                         children.ru_utime + children.ru_stime,
                          "self_cpu_seconds": usage.ru_utime + usage.ru_stime,
                          "child_cpu_seconds": children.ru_utime + children.ru_stime,
                          "peak_memory_kb": max(usage.ru_maxrss, children.ru_maxrss),
                          "peak_child_memory_kb": children.ru_maxrss,
                          "memory_scope": "maximum per-process RSS, not simultaneous aggregate RSS"}
    try:
        connection.send(message)
    finally:
        connection.close()


def _signal_worker(process, sig):
    # Production workers own a session; include their adapter subprocesses.
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        if process.is_alive():
            os.kill(process.pid, sig)


def _run_worker(node, seed, parents, limits, timeout):
    context = multiprocessing.get_context("fork")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(sender, node, seed, parents, limits))
    start = time.monotonic()
    process.start()
    sender.close()
    message = None
    received_eof = False
    try:
        if receiver.poll(timeout):
            try:
                message = receiver.recv()
            except EOFError:
                received_eof = True
        if message is None and process.is_alive() and not received_eof:
            _signal_worker(process, signal.SIGTERM)
            process.join(0.5)
            if process.is_alive():
                _signal_worker(process, signal.SIGKILL)
            message = {"status": "TIMEOUT", "error": "per-run or remaining wall budget exceeded"}
        process.join(max(0, timeout - (time.monotonic() - start)))
        if process.is_alive():
            _signal_worker(process, signal.SIGTERM)
            process.join(0.5)
            if process.is_alive():
                _signal_worker(process, signal.SIGKILL)
                process.join(0.5)
            message = {"status": "TIMEOUT", "error": "worker failed to exit within per-run wall budget"}
        if message is None:
            status = "BUDGET_EXCEEDED" if process.exitcode in (
                -signal.SIGXCPU, -signal.SIGKILL) else "FAILED"
            message = {"status": status, "error": f"worker exited {process.exitcode}"}
        message.setdefault("runtime", {"wall_seconds": time.monotonic() - start,
                                       "cpu_seconds": limits["cpu_seconds"],
                                       "peak_memory_kb": None})
        return message
    finally:
        receiver.close()
        if process.is_alive():
            _signal_worker(process, signal.SIGKILL)
            process.join(0.5)
        if not process.is_alive():
            process.close()


def _summary(records, output, config):
    # Pair within a seed, then cluster all stresses/nodes within that seed.
    groups = {}
    node_data = {}
    counts = {"rms": dict(tp=0, tn=0, fp=0, fn=0, errors=0, trials=0),
              "maxabs": dict(tp=0, tn=0, fp=0, fn=0, errors=0, trials=0)}
    for record in records:
        if record["status"] != "SUCCESS" or record["adapter"] != "signal_baseline":
            continue
        data = _read_object(output, record["artifact_id"])["data"]
        node_data[(record["node"], record["seed"])] = data
        groups.setdefault(record["seed"], []).append(
            data["counts"]["maxabs"]["errors"] - data["counts"]["rms"]["errors"])
        for method in counts:
            for key in counts[method]:
                counts[method][key] += data["counts"][method][key]
    pairs = [statistics.mean(values) for values in groups.values()]
    estimate = statistics.mean(pairs) if pairs else None
    # Distribution-free Hoeffding bound for independent bounded seed clusters.
    # Differences are in [-1,1]; unlike trial-level normal CIs, n=1 is honest.
    radius = math.sqrt(2 * math.log(40) / len(pairs)) if pairs else None
    interval = [max(-1, estimate - radius), min(1, estimate + radius)] if pairs else None
    expected_seeds = set(config["protocol"][config["protocol"]["run_split"]])
    baseline_nodes = [n["id"] for n in config["nodes"] if n["adapter"] == "signal_baseline"]
    complete = bool(baseline_nodes) and all(
        any(r["node"] == node and r["seed"] == seed and r["status"] == "SUCCESS"
            for r in records) for node in baseline_nodes for seed in expected_seeds)
    indexed = {(record["node"], record["seed"]): record for record in records}
    configured = {node["id"]: node for node in config["nodes"]}
    conditions = []
    for node_id in baseline_nodes:
        node = configured[node_id]
        generator = configured[node["parents"][0]]
        outcomes, status_counts = [], {}
        errors = {"rms": 0, "maxabs": 0}
        differences = []
        for seed in sorted(expected_seeds):
            record = indexed.get((node_id, seed))
            status = record["status"] if record else "PENDING"
            status_counts[status] = status_counts.get(status, 0) + 1
            outcome = {"seed": seed, "status": status,
                       "execution_seed": record["execution_seed"] if record else execution_seed(
                           digest(config), node_id, config["protocol"]["run_split"], seed)}
            data = node_data.get((node_id, seed))
            if data is not None:
                outcome.update({"counts": data["counts"],
                                "event_reference": data["event_reference"],
                                "missing_count": data["missing_count"]})
                for method in errors:
                    errors[method] += data["counts"][method]["errors"]
                differences.append(data["counts"]["maxabs"]["errors"] -
                                   data["counts"]["rms"]["errors"])
            elif record:
                outcome["error"] = record.get("error")
            outcomes.append(outcome)
        condition_complete = len(differences) == len(expected_seeds)
        condition_radius = math.sqrt(2 * math.log(40) / len(differences)) if differences else None
        condition_effect = statistics.mean(differences) if differences else None
        conditions.append({
            "node": node_id, "generator": generator["id"],
            "generator_params": generator["params"], "baseline_params": node["params"],
            "stress": generator["params"]["stress"], "evidence_origin": "synthetic",
            "run_split": config["protocol"]["run_split"], "complete": condition_complete,
            "status_counts": status_counts, "seed_outcomes": outcomes,
            "independent_seed_count": len(differences),
            "failure_intervals": {
                method: {**failure_interval(errors[method], len(differences)),
                         "independent_unit": "seed",
                         "assumption": "one Bernoulli event-presence error per independent seed"}
                if condition_complete and differences else None for method in errors
            },
            "seed_paired_error_difference": condition_effect,
            "ci95": [max(-1, condition_effect - condition_radius),
                     min(1, condition_effect + condition_radius)]
            if condition_complete and differences else None,
            "ci_method": "bounded independent seed Hoeffding; not a sign-flip range",
            "inference": "conditional on independent seeds; incomplete conditions have no intervals",
            "sign_flip_test": "NOT_COMPUTED: protocol does not justify null exchangeability/symmetry",
            "latency": "NOT_IMPLEMENTED: event presence only, not onset localization",
            "stress_scope": {"local": "time-local single-channel impulse",
                             "shared": "time-shared single-channel offset"}.get(
                                 generator["params"]["stress"], "single-channel time samples"),
            "multichannel_validation": "NOT_IMPLEMENTED",
        })
    return {
        "counts": counts, "independent_seed_clusters": len(pairs),
        "counts_interpretation": "descriptive pooled counts; multiple conditions within a seed "
                                 "are correlated, not independent Bernoulli trials",
        "conditions": conditions,
        "seed_paired_error_difference": estimate, "ci95": interval,
        "ci_method": "bounded independent seed-cluster Hoeffding; clipped to [-1,1]",
        "complete": complete,
        "practical_threshold": config["protocol"]["practical_threshold"],
        "threshold_supported": bool(complete and interval and
                                    interval[1] < -config["protocol"]["practical_threshold"]),
        "interpretation": "exploratory synthetic pulse presence only; independence assumes "
                          "distinct generator seeds, never independent legacy calibrations",
        "no_scientific_aggregate_score": True,
    }


def _export(output, records, summary):
    results = {"runs": records, "signal_comparison": summary}
    _atomic(output / "results.json", canonical(results))
    stream = io.StringIO(newline="")
    columns = ("node", "seed", "adapter", "status", "evidence_origin", "artifact_id", "error",
               "execution_seed", "criterion_passed")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(record)
    _atomic(output / "results.csv", stream.getvalue().encode())
    rows = "".join("<tr>" + "".join("<td>" + html.escape(str(record.get(key, ""))) +
                                   "</td>" for key in columns) + "</tr>" for record in records)
    page = ("<!doctype html><meta charset='utf-8'><title>Exploratory local evidence</title>"
            "<h1>Exploratory local evidence — not independently preregistered</h1>"
            "<p>All implemented evidence is synthetic; legacy identifies source lineage. "
            "No upstream compatibility claim "
            "or scientific aggregate score.</p><table><thead><tr>" +
            "".join("<th>" + key + "</th>" for key in columns) +
            "</tr></thead><tbody>" + rows + "</tbody></table><pre>" +
            html.escape(json.dumps(summary, indent=2)) + "</pre>")
    _atomic(output / "results.html", page.encode())


def execute(config, output, extended=False):
    """Execute dev-only smoke or explicitly extended plan; resume a verified identity.

    Linux is required for fork and enforced RLIMIT_AS/RLIMIT_CPU. All seeds and
    nodes get terminal records, even when budgets stop execution. Failures are
    immutable on resume; replay uses their capsule in a fresh output directory.
    """
    started = time.monotonic()
    if type(extended) is not bool:
        raise ValueError("extended must be boolean")
    plan = validate_config(config)
    if sys.platform != "linux":
        raise ValueError("execution requires Linux process resource limits")
    caps = EXTENDED_CAPS if extended else SMOKE_CAPS
    for key, cap in caps.items():
        if config["budgets"][key] > cap:
            raise ValueError(f"{key} exceeds {'extended' if extended else 'smoke'} cap {cap}")
    if plan["node_seed_runs"] > caps["max_runs"]:
        raise ValueError(f"planned node-seed records exceed selected cap {caps['max_runs']}")
    if not extended and config["protocol"]["run_split"] != "dev":
        raise ValueError("smoke runs may use dev seeds only; calibration requires --extended")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".execution.lock"
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("output is already locked; inspect interrupted writer before removing lock")
    os.close(lock_fd)
    try:
        identity = {"config": config, "config_hash": digest(config),
                    "dataset_hash": digest({"protocol": config["protocol"],
                                            "nodes": config["nodes"]}),
                    "sources": source_lock(), "dependency_lock": dependency_lock(),
                    "extended": extended, "seed_derivation": "sha256-node-partition-v1"}
        if any(node["adapter"] == "oes32_residual" for node in plan["nodes"]):
            identity["public_source_pin"] = public_source_pin()
        run_id = digest(identity)
        records, runtimes = [], []
        prior_wall = 0
        if (output / "manifest.json").exists():
            verify(output, _allow_incomplete=True)
            old = json.loads((output / "manifest.json").read_bytes())
            if old["run_id"] != run_id:
                raise ValueError("resume identity mismatch (config/dataset/source/runtime)")
            records, runtimes = old["runs"], old["runtime"]["runs"]
            prior_wall = old["runtime"]["cumulative_wall_seconds"]
        elif any(output.iterdir()) and any(p.name != lock.name for p in output.iterdir()):
            raise ValueError("nonempty output without a manifest; use a fresh output directory")
        identity_id = _object(output, identity)
        indexed = {(record["node"], record["seed"]): record for record in records}
        attempts = sum(r["attempted"] for r in records)
        cpu_used = sum(r["cpu_seconds"] for r in runtimes)

        def save(complete=False):
            summary = _summary(records, output, config)
            _export(output, records, summary)
            exports = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                       for name in ("results.json", "results.csv", "results.html")}
            runtime = {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "runs": runtimes,
                       "cumulative_wall_seconds": prior_wall + (time.monotonic() - started),
                       "cpu_seconds_used": sum(item["cpu_seconds"] for item in runtimes),
                       "attempts": sum(record["attempted"] for record in records)}
            accounting = {"kind": "budget_accounting", "run_id": run_id, **runtime}
            accounting_id = _object(output, accounting)
            manifest = {"version": 1, "run_id": run_id, "identity_id": identity_id,
                        "runs": records, "complete": complete, "exports": exports,
                        "accounting_id": accounting_id,
                        "evidence": "local exploratory evidence; no upstream compatibility claim",
                        "runtime": runtime}
            _atomic(output / "manifest.json", canonical(manifest))
            return manifest

        save()
        for seed in plan["seeds"]:
            for node in plan["nodes"]:
                key = (node["id"], seed)
                if key in indexed:
                    continue
                parents = [indexed[(parent, seed)] for parent in node["parents"]]
                record = {"node": node["id"], "seed": seed, "adapter": node["adapter"],
                          "adapter_version": adapters.VERSIONS[node["adapter"]],
                          "evidence_origin": node["contract"]["evidence_origin"],
                          "parent_artifact_ids": [p.get("artifact_id") for p in parents],
                          "execution_seed": execution_seed(identity["config_hash"], node["id"],
                                                           config["protocol"]["run_split"], seed),
                          "attempted": False}
                remaining_wall = config["budgets"]["wall_seconds"] - prior_wall - (
                    time.monotonic() - started)
                if adapters.VERSIONS[node["adapter"]] == "NOT_IMPLEMENTED":
                    message = {"status": "BLOCKED", "error": "adapter NOT_IMPLEMENTED"}
                elif any(p["status"] != "SUCCESS" for p in parents):
                    message = {"status": "BLOCKED", "error": "parent did not succeed"}
                elif attempts >= config["budgets"]["max_runs"] or remaining_wall <= 0 or (
                        cpu_used >= config["budgets"]["cpu_seconds"]):
                    message = {"status": "SKIPPED", "error": "total run/wall/CPU budget exhausted"}
                else:
                    record["attempted"] = True
                    attempts += 1
                    limits = dict(config["budgets"])
                    limits["cpu_seconds"] = max(0.01, limits["cpu_seconds"] - cpu_used)
                    data = [_read_object(output, p["artifact_id"])["data"] for p in parents]
                    message = _run_worker(node, record["execution_seed"], data, limits,
                                          min(remaining_wall, limits["per_run_seconds"]))
                runtime = message.pop("runtime", None)
                if runtime:
                    cpu_used += runtime["cpu_seconds"]
                    runtimes.append({"node": node["id"], "seed": seed,
                                     "execution_seed": record["execution_seed"], **runtime})
                record["status"] = message["status"]
                if message["status"] == "SUCCESS":
                    if node["adapter"] == "oes32_residual":
                        record["criterion_passed"] = message["data"]["result"]["passed"]
                    payload = {"run_id": run_id, "node": node, "seed": seed,
                               "execution_seed": record["execution_seed"],
                               "adapter_version": record["adapter_version"],
                               "parent_artifact_ids": record["parent_artifact_ids"],
                               "contract": node["contract"], "data": message["data"]}
                    record["artifact_id"] = _object(output, payload)
                else:
                    record["error"] = message["error"]
                    capsule = {"run_id": run_id, "config": config, "node": node, "seed": seed,
                               "execution_seed": record["execution_seed"],
                               "sources": identity["sources"], "dependency_lock": identity["dependency_lock"],
                               "parent_artifact_ids": record["parent_artifact_ids"],
                               "status": record["status"], "error": record["error"],
                               "replay": "Replay the full locked DAG in a fresh directory; no shell commands."}
                    record["capsule_id"] = _object(output, capsule)
                records.append(record)
                indexed[key] = record
                save()
        return save(complete=True)
    finally:
        lock.unlink()


def verify(output, _allow_incomplete=False):
    """Verify object digests, provenance links, exports and current local sources.

    Hashes detect corruption, not authenticity: no signatures or remote attestation.
    Runtime timestamps/accounting are intentionally outside deterministic identity.
    """
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_bytes())
    identity = _read_object(output, manifest["identity_id"])
    if digest(identity) != manifest["run_id"]:
        raise ValueError("run identity mismatch")
    config = identity["config"]
    plan = validate_config(config)
    if identity.get("seed_derivation") != "sha256-node-partition-v1":
        raise ValueError("unsupported seed derivation identity")
    if identity["config_hash"] != digest(config) or identity["dataset_hash"] != digest(
            {"protocol": config["protocol"], "nodes": config["nodes"]}):
        raise ValueError("config/dataset identity mismatch")
    if identity["sources"] != source_lock():
        raise ValueError("local source identity mismatch")
    if identity["dependency_lock"] != dependency_lock():
        raise ValueError("dependency/runtime identity mismatch")
    if any(node["adapter"] == "oes32_residual" for node in plan["nodes"]) and (
            identity.get("public_source_pin") != public_source_pin()):
        raise ValueError("public source dependency identity mismatch")
    caps = EXTENDED_CAPS if identity["extended"] else SMOKE_CAPS
    if any(config["budgets"][key] > cap for key, cap in caps.items()):
        raise ValueError("recorded budget exceeds selected cap")
    if plan["node_seed_runs"] > caps["max_runs"]:
        raise ValueError("recorded plan exceeds selected cap")
    if not identity["extended"] and config["protocol"]["run_split"] != "dev":
        raise ValueError("heldout/calibration use in smoke identity")
    nodes = {node["id"]: node for node in plan["nodes"]}
    expected = {(node["id"], seed) for seed in plan["seeds"] for node in plan["nodes"]}
    seen = {}
    for record in manifest["runs"]:
        key = (record["node"], record["seed"])
        if key not in expected or key in seen:
            raise ValueError("duplicate or unexpected run record")
        node = nodes[record["node"]]
        derived_seed = execution_seed(identity["config_hash"], node["id"],
                                      config["protocol"]["run_split"], record["seed"])
        _number(record["execution_seed"], "execution_seed", 0, 2**64 - 1, integer=True)
        if record["execution_seed"] != derived_seed:
            raise ValueError("derived execution seed mismatch")
        if record["status"] not in STATUSES or record["adapter"] != node["adapter"]:
            raise ValueError("invalid run status/adapter")
        if type(record["attempted"]) is not bool or (
                record["status"] in ("SUCCESS", "FAILED", "TIMEOUT", "BUDGET_EXCEEDED")
                and not record["attempted"]) or (
                record["status"] == "SKIPPED" and record["attempted"]):
            raise ValueError("inconsistent attempt status")
        if record["adapter_version"] != adapters.VERSIONS[node["adapter"]] or (
                record["evidence_origin"] != node["contract"]["evidence_origin"]):
            raise ValueError("adapter version/evidence mismatch")
        parents = [seen.get((parent, record["seed"])) for parent in node["parents"]]
        if any(parent is None for parent in parents):
            raise ValueError("parent missing or out of order")
        if record["parent_artifact_ids"] != [p.get("artifact_id") for p in parents]:
            raise ValueError("parent identity mismatch")
        if record["status"] == "SUCCESS":
            if any(p["status"] != "SUCCESS" for p in parents):
                raise ValueError("successful run has unsuccessful parent")
            payload = _read_object(output, record["artifact_id"])
            if any(payload[field] != value for field, value in (
                ("run_id", manifest["run_id"]), ("node", node), ("seed", record["seed"]),
                ("execution_seed", derived_seed),
                ("adapter_version", record["adapter_version"]),
                ("contract", node["contract"]),
                ("parent_artifact_ids", record["parent_artifact_ids"]))):
                raise ValueError("artifact provenance mismatch")
            _validate_adapter_data(node, payload["data"])
            if node["adapter"] == "oes32_residual":
                from public_residual_adapter import inspect_prepared
                if payload["data"]["source"] != inspect_prepared(node["params"]["source_directory"]):
                    raise ValueError("prepared public source changed")
                _boolean(record["criterion_passed"], "criterion_passed")
                if record["criterion_passed"] != payload["data"]["result"]["passed"]:
                    raise ValueError("criterion status mismatch")
        else:
            capsule = _read_object(output, record["capsule_id"])
            if any(capsule[field] != value for field, value in (
                ("run_id", manifest["run_id"]), ("config", config), ("node", node),
                ("seed", record["seed"]), ("sources", identity["sources"]),
                ("execution_seed", derived_seed),
                ("dependency_lock", identity["dependency_lock"]),
                ("parent_artifact_ids", record["parent_artifact_ids"]),
                ("status", record["status"]), ("error", record["error"]))):
                raise ValueError("failure capsule identity mismatch")
        seen[key] = record
    if sum(record["attempted"] for record in manifest["runs"]) > config["budgets"]["max_runs"]:
        raise ValueError("recorded attempts exceed max_runs")
    _validate_accounting(output, manifest)
    if manifest["complete"] and set(seen) != expected:
        raise ValueError("complete manifest omits runs")
    if not manifest["complete"] and not _allow_incomplete:
        raise ValueError("execution incomplete (resume with run)")
    for path in (output / "objects").glob("*.json"):
        _read_object(output, path.stem)
    for name in ("results.json", "results.csv", "results.html"):
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != manifest["exports"][name]:
            raise ValueError(f"export digest mismatch: {name}")
    results = json.loads((output / "results.json").read_bytes())
    if results != {"runs": manifest["runs"],
                   "signal_comparison": _summary(manifest["runs"], output, config)}:
        raise ValueError("exported results disagree with manifest or recomputed summary")
    return {"valid": True, "run_id": manifest["run_id"], "runs": len(seen),
            "complete": manifest["complete"]}


def replay(output, capsule_id, destination):
    """Replay a capsule's locked config, preserving all parent dependencies."""
    verify(output)
    capsule = _read_object(Path(output), capsule_id)
    if "replay" not in capsule:
        raise ValueError("object is not a failure capsule")
    manifest = json.loads((Path(output) / "manifest.json").read_bytes())
    if not any(record.get("capsule_id") == capsule_id for record in manifest["runs"]):
        raise ValueError("capsule is not part of this manifest")
    if Path(destination).resolve() == Path(output).resolve():
        raise ValueError("replay requires a fresh output directory")
    identity = _read_object(Path(output), manifest["identity_id"])
    return execute(capsule["config"], destination, extended=identity["extended"])
