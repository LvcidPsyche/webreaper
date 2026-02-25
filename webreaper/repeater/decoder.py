"""Stateless decoder/encoder utilities (Burp Decoder-like)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import json
from typing import Any
from urllib.parse import quote, unquote


def _to_bytes(value: str) -> bytes:
    return value.encode("utf-8", errors="replace")


def _b64_encode(value: str) -> str:
    return base64.b64encode(_to_bytes(value)).decode("ascii")


def _b64_decode(value: str) -> str:
    raw = base64.b64decode(value, validate=False)
    return raw.decode("utf-8", errors="replace")


def _hex_encode(value: str) -> str:
    return _to_bytes(value).hex()


def _hex_decode(value: str) -> str:
    raw = bytes.fromhex(value.strip())
    return raw.decode("utf-8", errors="replace")


def _jwt_parse(value: str) -> dict[str, Any]:
    parts = value.split(".")
    if len(parts) < 2:
        raise ValueError("Not a JWT (expected at least header.payload)")

    def _b64url_json(part: str) -> Any:
        padded = part + "=" * (-len(part) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return raw.decode("utf-8", errors="replace")

    sig = parts[2] if len(parts) > 2 else ""
    return {
        "header": _b64url_json(parts[0]),
        "payload": _b64url_json(parts[1]),
        "signature": sig,
        "signature_sha256": hashlib.sha256(sig.encode("utf-8")).hexdigest() if sig else None,
    }


def transform(operation: str, value: str) -> dict[str, Any]:
    op = (operation or "").strip().lower()
    try:
        if op == "url_encode":
            out: Any = quote(value, safe="")
        elif op == "url_decode":
            out = unquote(value)
        elif op == "base64_encode":
            out = _b64_encode(value)
        elif op == "base64_decode":
            out = _b64_decode(value)
        elif op == "html_encode":
            out = html.escape(value, quote=True)
        elif op == "html_decode":
            out = html.unescape(value)
        elif op == "hex_encode":
            out = _hex_encode(value)
        elif op == "hex_decode":
            out = _hex_decode(value)
        elif op == "jwt_parse":
            out = _jwt_parse(value)
        else:
            raise ValueError(f"Unsupported decoder operation: {operation}")
        return {"ok": True, "operation": op, "output": out}
    except (ValueError, binascii.Error) as e:
        return {"ok": False, "operation": op, "error": str(e)}
