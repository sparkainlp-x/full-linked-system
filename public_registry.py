"""Offline validation of an explicitly public-source inventory.

The manifest records observations, not authenticated provenance. It never
discovers repositories or fetches their contents during experiment execution.
"""
import json
from pathlib import Path
import re


CLASSIFICATIONS = {
    "runnable adapter", "candidate requiring inspection", "parallel experiment",
    "presentation-only", "placeholder", "excluded",
}
FIELDS = {
    "name", "url", "visibility", "inspected_sha", "license", "entry_points",
    "assumptions", "conventions", "inputs", "outputs", "dependencies",
    "evidence_status", "classification", "reason", "execution_status",
    "adapter_status", "code_copy_allowed",
}


def validate_inventory(inventory):
    if (not isinstance(inventory, dict) or type(inventory.get("schema_version")) is not int
            or inventory["schema_version"] != 1):
        raise ValueError("unsupported public inventory schema")
    if type(inventory.get("complete")) is not bool:
        raise ValueError("inventory completeness must be explicit")
    if not isinstance(inventory.get("discovery"), dict):
        raise ValueError("discovery evidence is required")
    if not isinstance(inventory.get("repositories"), list):
        raise ValueError("repositories must be an explicit list")
    discovered = inventory.get("public_repository_names", [])
    if (not isinstance(discovered, list) or any(not isinstance(name, str) for name in discovered)
            or len(set(discovered)) != len(discovered)):
        raise ValueError("discovered public names must be unique strings")
    defaults = inventory.get("discovery_only_defaults")
    if discovered and (not isinstance(defaults, dict) or {"name", "url"} & defaults.keys()):
        raise ValueError("discovery-only entries require explicit metadata defaults")
    repositories = list(inventory["repositories"])
    inspected_names = {r.get("name") for r in repositories if isinstance(r, dict)}
    for name in discovered:
        if name not in inspected_names:
            repositories.append({**defaults, "name": name,
                                 "url": f"https://github.com/sparkainlp-x/{name}"})
    names = set()
    for repo in repositories:
        if not isinstance(repo, dict) or not FIELDS <= repo.keys():
            raise ValueError("missing inventory fields")
        name = repo["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in names:
            raise ValueError("invalid or duplicate public project name")
        names.add(name)
        if repo["visibility"] != "public" or repo["url"] != f"https://github.com/sparkainlp-x/{name}":
            raise ValueError("only explicit public owner URLs are allowed")
        sha = repo["inspected_sha"]
        if sha is not None and (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)):
            raise ValueError("inspected revision must be a full SHA or null")
        if repo["classification"] not in CLASSIFICATIONS:
            raise ValueError("unrecognized integration classification")
        if repo["execution_status"] not in ("not run", "passed", "failed", "blocked", "skipped"):
            raise ValueError("invalid execution status")
        if repo["adapter_status"] not in ("IMPLEMENTED", "NOT_IMPLEMENTED"):
            raise ValueError("adapter implementation must be explicit")
        license_info = repo["license"]
        if (not isinstance(license_info, dict) or
                not {"status", "spdx", "path"} <= license_info.keys()):
            raise ValueError("license review evidence is required")
        if license_info["status"] not in ("inspected", "missing", "unclear", "not inspected"):
            raise ValueError("invalid license status")
        if type(repo["code_copy_allowed"]) is not bool:
            raise ValueError("code-copy permission must be explicit")
        if repo["code_copy_allowed"] and (license_info["status"] != "inspected" or sha is None):
            raise ValueError("missing license or inspected source blocks copying")
        if repo["classification"] == "runnable adapter" and repo["adapter_status"] != "IMPLEMENTED":
            raise ValueError("a candidate is not a runnable adapter")
        for field in ("entry_points", "assumptions", "dependencies"):
            if not isinstance(repo[field], list):
                raise ValueError(f"{field} must be a list")
        for field in ("reason", "evidence_status"):
            if not isinstance(repo[field], str) or not repo[field]:
                raise ValueError(f"{field} must state inspection limits")
    return {**inventory, "repositories": repositories}


def load_inventory(path):
    def reject_constant(value):
        raise ValueError(f"non-finite JSON value: {value}")

    return validate_inventory(json.loads(Path(path).read_text(), parse_constant=reject_constant))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--export", action="store_true", help="emit expanded registry with one record per public URL")
    args = parser.parse_args()
    inventory = load_inventory(args.manifest)
    print(json.dumps(inventory if args.export else
                     {"verified_manifest_entries": len(inventory["repositories"]),
                      "meaning": "schema validation only; not proof of visibility or truth"}))
