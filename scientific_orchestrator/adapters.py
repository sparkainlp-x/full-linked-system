"""Local stdlib adapters. No network access, shell commands, or implicit transforms."""

import math
import random

from public_residual_adapter import VERSION as OES32_VERSION

VERSIONS = {
    "signal_generator": "1",
    "signal_baseline": "1",
    "legacy_chain": "1",
    "oes32_residual": OES32_VERSION,
    "public_adapter": "NOT_IMPLEMENTED",
    "dimension_transform": "NOT_IMPLEMENTED",
}
TRANSFORMS = {}  # No dimension-changing transforms are implemented.
STRESSES = ("clean", "null", "shuffle", "noise", "drift", "missing", "local", "shared")


def signal_generator(params, seed, parents):
    rng = random.Random(seed)
    count = params["samples"]
    rate = params["sample_rate"]
    start, end = count // 3, count // 3 + max(1, count // 8)
    stress = params["stress"]
    event = stress != "null"
    values = [params["amplitude"] if event and start <= i < end else 0.0
              for i in range(count)]
    shared = rng.gauss(0, params["noise_sigma"]) if stress == "shared" else 0.0
    missing = 0
    for i in range(count):
        sigma = params["noise_sigma"] * (3 if stress == "noise" else 1)
        values[i] += rng.gauss(0, sigma) + shared
        if stress == "drift":
            values[i] += params["amplitude"] * i / count
        if stress == "local" and i == count // 2:
            values[i] += 2 * params["amplitude"]
        if stress == "missing" and rng.random() < params["missing_probability"]:
            values[i] = None
            missing += 1
    if stress == "shuffle":
        rng.shuffle(values)
    return {"values": values, "event_reference": event,
            "reference_window_seconds": [start / rate, end / rate],
            "missing_count": missing, "stress": stress,
            "reference_kind": "locked synthetic pulse presence, not event localization",
            "stress_scope": {"local": "time-local single-channel impulse",
                             "shared": "time-shared single-channel offset"}.get(
                                 stress, "single-channel time samples"),
            "multichannel_validation": "NOT_IMPLEMENTED"}


def _detection_report(metric, threshold, truth):
    prediction = metric >= threshold
    state = ("DETECTED" if prediction else "MISSED") if truth else (
        "FALSE_ALARM" if prediction else "TRUE_NULL")
    return {"metric": metric, "event": prediction, "event_state": state,
            "counts": {
                "tp": int(prediction and truth), "tn": int(not prediction and not truth),
                "fp": int(prediction and not truth), "fn": int(not prediction and truth),
                "errors": int(prediction != truth), "trials": 1,
            },
            "latency": {"status": "NOT_IMPLEMENTED", "seconds": None,
                        "reason": "event-presence detector, not onset localization",
                        "event_state": state, "missed_events": int(truth and not prediction)}}


def _observed_samples(values, threshold, event_reference):
    if not isinstance(values, list) or not 1 <= len(values) <= 4096:
        raise ValueError("baseline values require 1..4096 samples")
    if type(event_reference) is not bool:
        raise ValueError("event_reference must be boolean")
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or
            not 0 <= threshold <= 1000 or not math.isfinite(threshold)):
        raise ValueError("threshold must be a finite number in [0,1000], not bool")
    observed = []
    for value in values:
        if value is None:
            continue
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                abs(value) > 1e100 or not math.isfinite(value)):
            raise ValueError("samples must be finite numeric amplitudes, not bool")
        observed.append(value)
    if not observed:
        raise ValueError("all samples missing; no imputation is permitted")
    return observed


def rms_baseline(values, threshold, event_reference):
    """Independent RMS component; removing maxabs does not change this detector."""
    observed = _observed_samples(values, threshold, event_reference)
    metric = math.sqrt(sum(x * x for x in observed) / len(observed))
    return _detection_report(metric, threshold, event_reference)


def maxabs_baseline(values, threshold, event_reference):
    """Independent maxabs component; removing RMS does not change this detector."""
    observed = _observed_samples(values, threshold, event_reference)
    return _detection_report(max(abs(x) for x in observed), threshold, event_reference)


def signal_baseline(params, seed, parents):
    source = parents[0]
    observed = [x for x in source["values"] if x is not None]
    if not observed:
        raise ValueError("all samples missing; no imputation is permitted")
    truth = source["event_reference"]
    rms_result = rms_baseline(source["values"], params["rms_threshold"], truth)
    maxabs_result = maxabs_baseline(source["values"], params["maxabs_threshold"], truth)
    rms, maxabs = rms_result["metric"], maxabs_result["metric"]
    counts = {"rms": rms_result["counts"], "maxabs": maxabs_result["counts"]}
    return {"values": [rms, maxabs], "rms": rms, "maxabs": maxabs,
            "event_reference": truth, "rms_event": rms_result["event"],
            "maxabs_event": maxabs_result["event"], "counts": counts,
            "event_states": {"rms": rms_result["event_state"],
                             "maxabs": maxabs_result["event_state"]},
            "latency": {"rms": rms_result["latency"], "maxabs": maxabs_result["latency"]},
            "coupling_benefit": "NOT_CLAIMED: independent RMS and maxabs components",
            "observed_samples": len(observed), "missing_count": source["missing_count"],
            "stress": source["stress"]}


def legacy_chain(params, seed, parents):
    # Legacy sources are imported, never changed. Internal RNGs remain fixed.
    from chain import FullLinkedSystem
    from nervous import noisy, rand_field

    system = FullLinkedSystem(seed=seed)
    system.calibrate()
    tau_before = system.system.tau
    patterns_before = [tuple(pattern) for pattern in system.system.patterns]
    count_before = len(patterns_before)
    rng = random.Random(seed)
    if params["probe"] == "null":
        probe, truth = rand_field(128, rng), 0
    else:
        probe = noisy(system.system.patterns[0], params["noise_sigma"], rng)
        truth = 1
    result = system.run(probe, f_hz=params["frequency"],
                        total_steps=params["steps"], truth=truth)
    tau_after = system.system.tau
    count_after = len(system.system.patterns)
    unchanged = (tau_before == tau_after and
                 patterns_before == [tuple(pattern) for pattern in system.system.patterns])
    if not unchanged:
        raise RuntimeError("legacy adapter changed frozen calibrated tau or stored patterns")
    return {
        "values": [{"decision": result.decision, "action": result.action,
                    "response": result.response, "displacement": result.displacement,
                    "p1": result.p1, "brier": result.brier,
                    "injection_attempts": result.attempts,
                    "injection_cost": result.attempts * 0.01,
                    "ledger_ok": result.ledger_ok}],
        "evidence_caveat": "Exploratory legacy regression, not independent sampling: "
                           "internal calibration seed 11 and injection seed 1234 are fixed.",
        "evidence_origin": "synthetic",
        "source_lineage": "legacy FullLinkedSystem",
        "measurement_status": "NOT_MEASURED: synthetic toy probes and simulated propulsion only",
        "latency": {"status": "NOT_IMPLEMENTED", "seconds": None},
        "calibration_invariants": {"tau_before": tau_before, "tau_after": tau_after,
                                   "patterns_before": count_before, "patterns_after": count_after,
                                   "tau_and_patterns_unchanged": unchanged},
        "cost_caveat": "All injection attempts charged, not only accepted variants; "
                       "calibration computation is included in runtime.",
    }


def oes32_residual(params, seed, parents):
    """Execute only the explicitly prepared, hash-pinned offline numerical API."""
    from public_residual_adapter import evaluate

    if parents:
        raise ValueError("oes32_residual has no parent interface")
    request = {key: params[key] for key in ("reference", "observed", "tolerance")}
    return evaluate(request, params["source_directory"], timeout=5)


FUNCTIONS = {
    "signal_generator": signal_generator,
    "signal_baseline": signal_baseline,
    "legacy_chain": legacy_chain,
    "oes32_residual": oes32_residual,
}
