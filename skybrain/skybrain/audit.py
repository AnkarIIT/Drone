"""Tamper-evident audit log: every record carries the hash of the previous one."""
from __future__ import annotations
import hashlib
import json


class AuditLog:
    def __init__(self) -> None:
        self.records: list[dict] = []

    @staticmethod
    def _hash(rec: dict) -> str:
        body = {k: v for k, v in rec.items() if k != "hash"}
        return hashlib.sha256(json.dumps(body, sort_keys=True, default=float).encode()).hexdigest()

    def append(self, kind: str, payload: dict) -> None:
        prev = self.records[-1]["hash"] if self.records else "0" * 64
        rec = {"i": len(self.records), "kind": kind, "payload": payload, "prev": prev}
        rec["hash"] = self._hash(rec)
        self.records.append(rec)

    def verify(self) -> bool:
        prev = "0" * 64
        for rec in self.records:
            if rec["prev"] != prev or rec["hash"] != self._hash(rec):
                return False
            prev = rec["hash"]
        return True

    def save(self, path: str) -> None:
        with open(path, "w") as fh:
            for rec in self.records:
                fh.write(json.dumps(rec, default=float) + "\n")
