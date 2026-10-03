"""Mètriques HTTP reals en memòria (latències i codis d'estat) per a la telemetria Superadmin.

Cap valor és inventat: si no hi ha mostres, els consumidors reben ``None``.
Les mètriques són per procés (reinici = buit) i només contenen durada i codi d'estat,
mai cap dada de negoci (Spec 04 FR-011, Zero Intrusió).
"""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple

_MAX_SAMPLES = 2000
_samples: Deque[Tuple[float, int]] = deque(maxlen=_MAX_SAMPLES)
_started_at = time.monotonic()


def record(duration_ms: float, status_code: int) -> None:
    """Registra una petició HTTP completada."""
    _samples.append((duration_ms, status_code))


def process_uptime_seconds() -> float:
    """Segons des que ha arrencat el procés del backend."""
    return time.monotonic() - _started_at


def _percentile(sorted_values: list[float], pct: float) -> float:
    idx = min(len(sorted_values) - 1, max(0, int(round(pct / 100.0 * (len(sorted_values) - 1)))))
    return sorted_values[idx]


def latency_percentiles() -> Optional[Dict[str, float]]:
    """p50/p95/p99 en ms o ``None`` si no hi ha mostres."""
    if not _samples:
        return None
    values = sorted(d for d, _ in _samples)
    return {
        "p50": round(_percentile(values, 50), 1),
        "p95": round(_percentile(values, 95), 1),
        "p99": round(_percentile(values, 99), 1),
        "samples": float(len(values)),
    }


def http_ratio() -> Optional[Dict[str, float]]:
    """Percentatge de 2xx-3xx / 4xx / 5xx o ``None`` si no hi ha mostres."""
    if not _samples:
        return None
    total = len(_samples)
    ok = sum(1 for _, s in _samples if s < 400)
    c4 = sum(1 for _, s in _samples if 400 <= s < 500)
    c5 = sum(1 for _, s in _samples if s >= 500)
    return {
        "2xx_3xx_percent": round(ok * 100.0 / total, 2),
        "4xx_percent": round(c4 * 100.0 / total, 2),
        "5xx_percent": round(c5 * 100.0 / total, 2),
    }
