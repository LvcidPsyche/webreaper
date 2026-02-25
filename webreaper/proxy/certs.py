"""HTTPS interception certificate status helpers."""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path
from typing import Any


DEFAULT_CERT_CANDIDATES = [
    Path.home() / '.mitmproxy' / 'mitmproxy-ca-cert.pem',
    Path.home() / '.mitmproxy' / 'mitmproxy-ca-cert.cer',
    Path.home() / '.mitmproxy' / 'mitmproxy-ca-cert.p12',
]


def _sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def cert_status(ca_cert_path: str | None = None) -> dict[str, Any]:
    candidates = [Path(ca_cert_path).expanduser()] if ca_cert_path else DEFAULT_CERT_CANDIDATES
    files = []
    primary = None
    for path in candidates:
        exists = path.exists()
        item = {
            'path': str(path),
            'exists': exists,
            'readable': os.access(path, os.R_OK) if exists else False,
            'size_bytes': path.stat().st_size if exists else None,
            'sha256': _sha256_file(path) if exists else None,
            'mtime': path.stat().st_mtime if exists else None,
        }
        if exists and primary is None:
            primary = item
        files.append(item)

    os_name = platform.system().lower()
    install_hints = {
        'darwin': 'Import mitmproxy CA in Keychain Access and mark as Always Trust.',
        'windows': 'Import mitmproxy CA into Trusted Root Certification Authorities (Current User or Local Machine).',
        'linux': 'Install CA into system/browser trust stores (varies by distro/browser). Firefox may use separate cert store.',
    }

    return {
        'tls_intercept_ready': bool(primary and primary['exists'] and primary['readable']),
        'primary_cert': primary,
        'candidates': files,
        'mitmproxy_dir': str((Path.home() / '.mitmproxy')),
        'os': os_name,
        'install_hint': install_hints.get(os_name, install_hints['linux']),
        'notes': [
            'This checks certificate file presence/readability only.',
            'It does not verify browser/system trust installation automatically.',
        ],
    }
