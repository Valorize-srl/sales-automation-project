"""In-memory lookup of Eolo's CAP → cluster classification.

Eolo classifies Italian comuni into commercial clusters (VERDE-FTTH, VERDE-FWA,
GIALLI, ROSSI, NO SELL). The /leads filter panel exposes the first three so
the user can target prospects in coverage areas.

Backed by `backend/app/data/eolo_cap_zones.csv` — slim two-column file
(`zip_code,cluster`) generated from Eolo's full coverage report. Update path:
replace the CSV in the repo and redeploy. The CSV is ~100KB / ~5000 rows,
so reload at startup is instant.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "eolo_cap_zones.csv"


class _EoloZones:
    def __init__(self) -> None:
        self._cluster_to_caps: dict[str, frozenset[str]] = {}
        self._load()

    def _load(self) -> None:
        if not _CSV_PATH.exists():
            logger.warning("Eolo zones CSV not found at %s — filter disabled", _CSV_PATH)
            return
        buckets: dict[str, set[str]] = {}
        with _CSV_PATH.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cap = (row.get("zip_code") or "").strip()
                cluster = (row.get("cluster") or "").strip()
                if not cap or not cluster:
                    continue
                buckets.setdefault(cluster, set()).add(cap)
        self._cluster_to_caps = {k: frozenset(v) for k, v in buckets.items()}
        logger.info(
            "Loaded Eolo zones: %s",
            ", ".join(f"{k}={len(v)}" for k, v in sorted(self._cluster_to_caps.items())),
        )

    def caps_for_clusters(self, clusters: Iterable[str]) -> set[str]:
        """Return the union of CAPs belonging to any of the requested clusters.

        Unknown cluster names are ignored silently. Empty input → empty set.
        """
        out: set[str] = set()
        for c in clusters:
            key = (c or "").strip().lower()
            out |= self._cluster_to_caps.get(key, frozenset())
        return out

    def known_clusters(self) -> set[str]:
        return set(self._cluster_to_caps.keys())


eolo_zones = _EoloZones()
