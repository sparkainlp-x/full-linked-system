"""Hash-chained run ledger, fail-closed, stdlib-only.
Each entry records the previous entry's hash, so a later
edit breaks the chain. The ledger records decisions; it
does not authorise them. Only actions move/hold/alert are
recorded; there is no other action type in this system.
"""
import hashlib
import json

ALLOWED_ACTIONS = ("move", "hold", "alert")


class Ledger:
    def __init__(self):
        self.entries = []
        self.prev_hash = "0" * 64

    def append(self, stage, detail, action):
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"action {action!r} not allowed")
        entry = {"index": len(self.entries),
                 "prev_hash": self.prev_hash,
                 "stage": stage, "detail": detail, "action": action}
        blob = json.dumps(entry, sort_keys=True).encode()
        entry["hash"] = hashlib.sha256(blob).hexdigest()
        self.prev_hash = entry["hash"]
        self.entries.append(entry)
        return entry

    def verify(self):
        prev = "0" * 64
        for e in self.entries:
            if e["prev_hash"] != prev:
                return False
            check = {k: v for k, v in e.items() if k != "hash"}
            blob = json.dumps(check, sort_keys=True).encode()
            if hashlib.sha256(blob).hexdigest() != e["hash"]:
                return False
            prev = e["hash"]
        return True
