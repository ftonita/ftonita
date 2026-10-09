"""Apply a plan to Vault (create-only, idempotent, resumable) and verify the result."""

from __future__ import annotations

from dataclasses import dataclass, field

from .backends import Backend, CasMismatch, VaultError
from .fingerprint import fingerprint
from .ledger import Entry, Ledger
from .models import LegacySecret, PlanItem


@dataclass
class Result:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    would_write: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.conflicts and not self.failed


def _metadata(s: LegacySecret) -> dict[str, str]:
    md = {"legacy_id": s.id, "kind": s.kind, "migrated_by": "vault-migration-toolkit"}
    if s.last_rotated:
        md["last_rotated"] = s.last_rotated.isoformat()
    return md


def apply(
    items: list[PlanItem],
    secrets: dict[str, LegacySecret],
    backend: Backend,
    ledger: Ledger,
    key: bytes,
    *,
    execute: bool,
    overwrite: bool = False,
    create_mounts: bool = False,
) -> Result:
    res = Result()
    for item in items:
        s, t = secrets[item.secret_id], item.target
        fp = fingerprint(key, s.value)
        try:
            current = backend.read(t.mount, t.path) if backend.mount_exists(t.mount) else None
            if current is not None and fingerprint(key, current.data.get("value", "")) == fp:
                res.skipped.append(s.id)
                if execute:
                    ledger.append(Entry(s.id, str(t), "skipped_identical", fp[:8]))
                continue
            if current is not None and not overwrite:
                res.conflicts.append(s.id)
                if execute:
                    ledger.append(
                        Entry(s.id, str(t), "conflict", fp[:8], "target exists with a different value")
                    )
                continue
            if not execute:
                res.would_write.append(s.id)
                continue
            if not backend.mount_exists(t.mount):
                if not create_mounts:
                    raise VaultError(f"mount {t.mount}/ does not exist (use --create-mounts)")
                backend.create_mount(t.mount)
            backend.write(
                t.mount, t.path, {"value": s.value.reveal()}, current.version if current else 0, _metadata(s)
            )
            res.written.append(s.id)
            ledger.append(Entry(s.id, str(t), "written", fp[:8]))
        except (VaultError, CasMismatch) as exc:
            res.failed.append(s.id)
            if execute:
                ledger.append(Entry(s.id, str(t), "failed", fp[:8], str(exc)))
    return res


@dataclass
class Verification:
    verified: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mismatched and not self.missing


def verify(
    items: list[PlanItem], secrets: dict[str, LegacySecret], backend: Backend, ledger: Ledger, key: bytes
) -> Verification:
    out = Verification()
    for item in items:
        s, t = secrets[item.secret_id], item.target
        fp = fingerprint(key, s.value)
        stored = backend.read(t.mount, t.path) if backend.mount_exists(t.mount) else None
        if stored is None:
            out.missing.append(s.id)
            ledger.append(Entry(s.id, str(t), "missing", fp[:8]))
        elif fingerprint(key, stored.data.get("value", "")) != fp:
            out.mismatched.append(s.id)
            ledger.append(Entry(s.id, str(t), "mismatch", fp[:8]))
        else:
            out.verified.append(s.id)
            ledger.append(Entry(s.id, str(t), "verified", fp[:8]))
    return out
