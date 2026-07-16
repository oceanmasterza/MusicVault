"""Built-in Chromaprint fingerprint provider (via pyacoustid / fpcalc).

AcoustID *HTTP* lookup is deferred to Phase 6 (MetadataWorker). This
module only generates Chromaprint bytes for :class:`FingerprintWorker`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import acoustid

from musicvault.models.interfaces.fingerprint import FingerprintResult


def generate_chromaprint(path: Path) -> FingerprintResult:
    """Run Chromaprint against ``path`` and return a typed result.

    Uses :func:`acoustid.fingerprint_file`, which prefers the chromaprint
    library when available and falls back to the ``fpcalc`` CLI. The raw
    fingerprint is stored as bytes (UTF-8 if pyacoustid returns ``str``)
    and ``fingerprint_hash`` is the SHA-256 of those bytes — matching
    docs/architecture/10-revision-v2.md's ``file_identity`` columns.
    """
    try:
        duration, fingerprint = acoustid.fingerprint_file(str(path))
    except acoustid.NoBackendError as exc:
        raise RuntimeError(
            "Chromaprint backend not found — install fpcalc or the chromaprint library"
        ) from exc
    except acoustid.FingerprintGenerationError as exc:
        raise RuntimeError(f"Chromaprint failed for {path}: {exc}") from exc

    if isinstance(fingerprint, bytes):
        fingerprint_data = fingerprint
    else:
        fingerprint_data = str(fingerprint).encode("utf-8")

    return FingerprintResult(
        duration_seconds=float(duration),
        fingerprint_data=fingerprint_data,
        fingerprint_hash=hashlib.sha256(fingerprint_data).hexdigest(),
    )


class ChromaprintFingerprintProvider:
    """:class:`~musicvault.models.interfaces.fingerprint.FingerprintProvider`
    implementation that wraps :func:`generate_chromaprint`."""

    def fingerprint_file(self, path: Path) -> FingerprintResult:
        return generate_chromaprint(path)
