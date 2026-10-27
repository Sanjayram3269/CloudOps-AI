"""Deterministic event fingerprinting and incident correlation."""
from __future__ import annotations

import hashlib
import re


_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b")
_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_NUMBER = re.compile(r"\b\d+\b")
_WHITESPACE = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    """Remove common high-cardinality values while retaining useful error context."""
    value = message.strip().lower()
    value = _UUID.sub("<uuid>", value)
    value = _HEX.sub("<hex>", value)
    value = _NUMBER.sub("<n>", value)
    return _WHITESPACE.sub(" ", value)


def fingerprint(service: str, environment: str, message: str) -> str:
    canonical = "|".join((service.strip().lower(), environment.strip().lower(), normalize_message(message)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
