"""python -m scientific_orchestrator {plan,run,verify,replay}."""

import argparse
import json
import sys

from .core import execute, load_config, replay, validate_config, verify


def main():
    parser = argparse.ArgumentParser(description="Bounded exploratory local science runner")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("config")
    run = commands.add_parser("run")
    run.add_argument("config")
    run.add_argument("--output", required=True)
    run.add_argument("--extended", action="store_true")
    check = commands.add_parser("verify")
    check.add_argument("output")
    again = commands.add_parser("replay")
    again.add_argument("output")
    again.add_argument("capsule_id")
    again.add_argument("--output", dest="destination", required=True)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = validate_config(load_config(args.config))
        elif args.command == "run":
            result = execute(load_config(args.config), args.output, args.extended)
        elif args.command == "verify":
            result = verify(args.output)
        else:
            result = replay(args.output, args.capsule_id, args.destination)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        if args.command in ("run", "replay") and any(
                record["status"] != "SUCCESS" for record in result["runs"]):
            return 2
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error), "type": type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
