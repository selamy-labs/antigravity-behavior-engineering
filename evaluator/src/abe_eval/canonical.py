"""Dependency-free canonical JSON bytes shared with runtime contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_SAFE_INTEGER = (1 << 53) - 1


def _assert_well_formed_unicode(value: str) -> None:
    for character in value:
        code_point = ord(character)
        if 0xD800 <= code_point <= 0xDFFF:
            raise TypeError("JSON strings must not contain unpaired surrogates")


def _serialize(value: Any, ancestors: set[int]) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        _assert_well_formed_unicode(value)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise TypeError("JSON integers must be safe integers")
        return str(value)
    if isinstance(value, float):
        raise TypeError("shared JSON contracts require integers or decimal strings")
    if isinstance(value, list):
        identifier = id(value)
        if identifier in ancestors:
            raise TypeError("JSON values must not be cyclic")
        ancestors.add(identifier)
        try:
            return "[" + ",".join(_serialize(item, ancestors) for item in value) + "]"
        finally:
            ancestors.remove(identifier)
    if isinstance(value, dict):
        identifier = id(value)
        if identifier in ancestors:
            raise TypeError("JSON values must not be cyclic")
        for key in value:
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _assert_well_formed_unicode(key)
        ancestors.add(identifier)
        try:
            sorted_keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
            return "{" + ",".join(
                json.dumps(key, ensure_ascii=False, separators=(",", ":"))
                + ":"
                + _serialize(value[key], ancestors)
                for key in sorted_keys
            ) + "}"
        finally:
            ancestors.remove(identifier)
    raise TypeError("unsupported JSON value; expected null, boolean, string, safe integer, array, or plain object")


def canonical_bytes(value: Any) -> bytes:
    """Return the UTF-8 bytes for the shared canonical JSON subset."""

    return _serialize(value, set()).encode("utf-8")


def sha256_digest(data: bytes) -> str:
    """Return a lower-case, prefixed SHA-256 digest for exact bytes."""

    if not isinstance(data, bytes):
        raise TypeError("sha256_digest expects bytes")
    return "sha256:" + hashlib.sha256(data).hexdigest()
