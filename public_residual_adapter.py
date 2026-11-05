"""Pinned, optional, offline OES-32 adapter; this is not stabilizer QEC.

No upstream implementation is vendored. Explicit preparation downloads only
three public files at the inspected revision into an isolated local directory.
Subprocess separation is not a security sandbox or an AGPL exemption.
"""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


UPSTREAM = "https://github.com/sparkainlp-x/oes32-residual"
REVISION = "fc0059bea09048baee0fc9c70d8de4d5da0d9493"
VERSION = "1:" + REVISION
FILES = {
    "src/residual_reference.py": ("residual_reference.py", "75049803a8643f66427427b91a09b12636b2f00823cf4486e528fb8beb7611e3"),
    "LICENSE": ("LICENSE", "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"),
    "COMMERCIAL-LICENSE.md": ("COMMERCIAL-LICENSE.md", "e14ceefee61916fe93056b957eeaa11e8e96bdb7689f12fcef42bac770491bba"),
}
WRAPPER = """
import dataclasses, json, resource, sys, types
for kind, ceiling in ((resource.RLIMIT_AS, 128*1024*1024), (resource.RLIMIT_CPU, 2)):
    inherited = resource.getrlimit(kind)[1]
    bound = ceiling if inherited == resource.RLIM_INFINITY else min(ceiling, inherited)
    resource.setrlimit(kind, (bound, bound))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
payload = json.load(sys.stdin)
module = types.ModuleType('pinned_residual')
sys.modules[module.__name__] = module
exec(compile(payload['source'], 'inspected_residual_reference.py', 'exec'), module.__dict__)
result = module.evaluate_residual(**payload['request'])
print(json.dumps(dataclasses.asdict(result), allow_nan=False, sort_keys=True))
"""


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite JSON value: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a finite real number, not bool")
    try:
        if math.isfinite(value):
            return value
    except OverflowError:
        pass
    raise ValueError("expected a finite real number")


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {"reference", "observed", "tolerance"}:
        raise ValueError("request requires exactly reference, observed and tolerance")
    for name in ("reference", "observed"):
        values = request[name]
        if not isinstance(values, list) or len(values) != 32:
            raise ValueError(f"{name} must be exactly 32 real components")
        for value in values:
            finite(value)
    if finite(request["tolerance"]) < 0:
        raise ValueError("tolerance must be nonnegative")
    # Finite inputs alone do not prevent subtraction overflow.
    for left, right in zip(request["reference"], request["observed"]):
        finite(right - left)
    return request


def inspect_prepared(directory):
    directory = Path(directory).resolve()
    for target, expected in FILES.values():
        path = directory / target
        if not path.is_file():
            raise FileNotFoundError(f"BLOCKED: pinned public dependency missing: {target}")
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"pinned upstream file mismatch: {target}")
    return {
        "repository": UPSTREAM, "revision": REVISION,
        "license": "AGPL-3.0-only",
        "file_sha256": {target: expected for target, expected in FILES.values()},
        "trust": "byte consistency with inspected public source; not authenticated provenance",
    }


def prepare(directory, allow_network=False):
    """Explicit opt-in source preparation, never called by run()."""
    if allow_network is not True:
        raise ValueError("preparation requires explicit --allow-network")
    import urllib.request
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("preparation needs an empty isolated directory")
    directory.mkdir(parents=True, exist_ok=True)
    # Verify every response before writing any file; no guessed APIs or revisions.
    downloaded = {}
    for source, (target, expected) in FILES.items():
        url = f"https://raw.githubusercontent.com/sparkainlp-x/oes32-residual/{REVISION}/{source}"
        with urllib.request.urlopen(url, timeout=15) as response:
            content = response.read(100001)
        if len(content) > 100000 or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"public preparation hash mismatch: {source}")
        downloaded[target] = content
    for target, content in downloaded.items():
        with (directory / target).open("xb") as stream:
            stream.write(content)
    return inspect_prepared(directory)


def evaluate(request, directory, timeout=5):
    """Execute inspected numerical API; a failed residual criterion is valid data."""
    validate_request(request)
    if not 0.01 <= finite(timeout) <= 10:
        raise ValueError("timeout must be within 0.01..10 seconds")
    if sys.platform != "linux":
        raise RuntimeError("BLOCKED: adapter requires Linux resource limits")
    provenance = inspect_prepared(directory)
    source = (Path(directory).resolve() / "residual_reference.py").read_bytes()
    if hashlib.sha256(source).hexdigest() != FILES["src/residual_reference.py"][1]:
        raise ValueError("pinned source changed before execution")
    # Execute these exact checked bytes, not a second path read in the child.
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", WRAPPER],
        input=json.dumps({"request": request, "source": source.decode("utf-8")}, allow_nan=False),
        text=True, capture_output=True,
        timeout=timeout, check=True, shell=False,
    )
    if len(completed.stdout) > 20000:
        raise ValueError("upstream response exceeds bounded schema")
    result = strict_json(completed.stdout)
    fields = {"component_residuals", "aggregate_residual", "tolerance", "passed", "failed"}
    if not isinstance(result, dict) or set(result) != fields:
        raise ValueError("incompatible upstream output schema")
    components = result["component_residuals"]
    if not isinstance(components, list) or len(components) != 32:
        raise ValueError("upstream output must have exactly 32 residual components")
    expected = [abs(y - x) for x, y in zip(request["reference"], request["observed"])]
    if any(finite(value) < 0 for value in components) or components != expected:
        raise ValueError("upstream component residuals disagree with analytic reference")
    if finite(result["aggregate_residual"]) != max(expected) or finite(result["tolerance"]) != request["tolerance"]:
        raise ValueError("upstream aggregate/tolerance mismatch")
    passed = max(expected) <= request["tolerance"]
    if (type(result["passed"]) is not bool or type(result["failed"]) is not bool
            or result["passed"] != passed or result["failed"] == passed):
        raise ValueError("upstream strict failure criterion mismatch")
    return {
        "values": components, "result": result, "source": provenance,
        "evidence_origin": "synthetic", "execution_status": "passed",
        "interpretation": "reproduced numerical reference within stated synthetic conditions",
        "limitations": "Residual threshold gate, not stabilizer QEC or independent sensor validation",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--directory", required=True, type=Path)
    prep.add_argument("--allow-network", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("--request", required=True, type=Path)
    run.add_argument("--source-dir", required=True, type=Path)
    run.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.directory, args.allow_network)
    else:
        raw = args.request.read_bytes()
        if len(raw) > 20000:
            raise ValueError("request exceeds 20 KB")
        result = evaluate(strict_json(raw), args.source_dir, args.timeout)
    print(json.dumps(result, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
