"""Decision log — Clause 15.1.

Every verdict, automated or human, is logged with: timestamp, case ID, a full
Case File snapshot, the clauses cited, the verdict, the lane, and (for human
verdicts, appended later by n8n) whether the proposal was confirmed or amended.

JSONL is the v1 store: append-only, greppable, and trivially importable into a
Sheet for the Clause 15.2 amendment-rate KPI.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

log = logging.getLogger(__name__)
_LOCK = threading.Lock()


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    """Never write image bytes to the log — keep the hash-sized facts instead.

    Clause 13.6 wants an image-reuse check, so the byte length is retained as a
    cheap stand-in until a real perceptual hash is added.
    """
    ret = payload.get("return") or {}
    photo = ret.get("photo")
    if isinstance(photo, dict) and photo.get("base64"):
        scrubbed = dict(payload)
        scrubbed["return"] = {
            **ret,
            "photo": {
                "fileName": photo.get("fileName", ""),
                "mimeType": photo.get("mimeType", ""),
                "base64Bytes": len(photo.get("base64", "")),
            },
        }
        return scrubbed
    return payload


def write(
    *,
    request_id: str,
    payload: dict[str, Any],
    verdict: str,
    lane: str,
    cited_clauses: list[str],
    confidence: str,
    reasoning: str,
    deductions: list[dict[str, Any]],
    latency_ms: float,
) -> None:
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "caseId": request_id,
        "verdict": verdict,
        "lane": lane,
        "confidence": confidence,
        "citedClauses": cited_clauses,
        "reasoning": reasoning,
        "deductions": deductions,
        "policyVersion": config.POLICY_VERSION,
        "decidedBy": "engine",
        # Filled in by the n8n approve/amend step (Clause 15.2 KPI).
        "humanOutcome": None,
        "caseFile": _scrub(payload),
        "latencyMs": round(latency_ms, 1),
    }
    _append(row)


def write_human_outcome(
    *,
    case_id: str,
    outcome: str,
    final_verdict: str,
    adjudicator: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Record an adjudicator's confirm/amend against a case (Clauses 15.1, 15.2).

    The log is append-only: the engine's original row is never rewritten, so the
    divergence between proposal and final verdict stays auditable. `outcome` is
    'confirmed' or 'amended'; the amendment rate over these rows is the Clause
    15.2 KPI.
    """
    proposal = find_latest(case_id)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "caseId": case_id,
        "verdict": final_verdict,
        "lane": (proposal or {}).get("lane", "HUMAN_REVIEW"),
        "confidence": (proposal or {}).get("confidence"),
        "citedClauses": (proposal or {}).get("citedClauses", []),
        "reasoning": note,
        "deductions": [],
        "policyVersion": config.POLICY_VERSION,
        "decidedBy": "human",
        "humanOutcome": outcome,
        "proposedVerdict": (proposal or {}).get("verdict"),
        "adjudicator": adjudicator,
        "caseFile": (proposal or {}).get("caseFile"),
        "latencyMs": None,
    }
    _append(row)
    return row


def _append(row: dict[str, Any]) -> None:
    path: Path = config.DECISION_LOG_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, ensure_ascii=False, default=str)
        with _LOCK, path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:  # logging must never take the request down
        log.error("could not append to decision log %s: %s", path, exc)


def read_all() -> list[dict[str, Any]]:
    path: Path = config.DECISION_LOG_PATH
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def find_latest(case_id: str, decided_by: str = "engine") -> dict[str, Any] | None:
    """The most recent row for a case — the engine's proposal by default."""
    for row in reversed(read_all()):
        if row.get("caseId") == case_id and row.get("decidedBy") == decided_by:
            return row
    return None


def tail(limit: int = 20) -> list[dict[str, Any]]:
    """Most recent decisions, newest first — used by GET /decisions."""
    return read_all()[-limit:][::-1]
