"""Keyed fingerprints let us compare secrets (duplicates, verification) without storing them."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from .models import Secret


def load_or_create_key(directory: str | Path) -> bytes:
    """Per-migration random key, stored 0600 next to the ledger."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    key_file = d / "fingerprint.key"
    if key_file.exists():
        return key_file.read_bytes()
    key = os.urandom(32)
    fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def fingerprint(key: bytes, value: Secret | str) -> str:
    raw = value.reveal() if isinstance(value, Secret) else value
    return hmac.new(key, raw.encode("utf-8"), hashlib.sha256).hexdigest()
