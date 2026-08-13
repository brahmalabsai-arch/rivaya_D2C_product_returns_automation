"""Operating metrics computed from the decision log.

These are the numbers stage 5's README quotes, and the Clause 15.2 control:
where human adjudicators amend more than 10% of system proposals in a rolling
month, the policy-engine owner must review the divergence log and either fix the
logic or amend the policy document.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from . import decision_log

AMENDMENT_RATE_CEILING = 10.0  # percent — Clause 15.2

# Human baseline for the ROI line: ~5 minutes of adjudicator time per case.
HUMAN_BASELINE_SECONDS = 300


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def summary(window_days: int | None = 30) -> dict[str, Any]:
    rows = decision_log.read_all()
    if window_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        rows = [r for r in rows if (_parse(r.get("timestamp")) or cutoff) >= cutoff]

    engine = [r for r in rows if r.get("decidedBy") == "engine"]
    human = [r for r in rows if r.get("decidedBy") == "human"]

    total = len(engine)
    auto = sum(1 for r in engine if r.get("lane") == "AUTO")
    review = total - auto
    ambiguous = sum(1 for r in engine if r.get("confidence") == "AMBIGUOUS")

    confirmed = sum(1 for r in human if r.get("humanOutcome") == "confirmed")
    amended = sum(1 for r in human if r.get("humanOutcome") == "amended")
    resolved = confirmed + amended

    latencies = [r["latencyMs"] for r in engine if isinstance(r.get("latencyMs"), (int, float))]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

    amendment_rate = round(100 * amended / resolved, 1) if resolved else None

    return {
        "windowDays": window_days,
        "decisions": total,
        "straightThrough": {
            "auto": auto,
            "humanReview": review,
            "autoRatePct": round(100 * auto / total, 1) if total else None,
        },
        "confidence": {
            "clear": total - ambiguous,
            "ambiguous": ambiguous,
            "ambiguousRatePct": round(100 * ambiguous / total, 1) if total else None,
        },
        "humanAdjudication": {
            "resolved": resolved,
            "confirmed": confirmed,
            "amended": amended,
            "amendmentRatePct": amendment_rate,
            "ceilingPct": AMENDMENT_RATE_CEILING,
            # Clause 15.2 trigger for a divergence review.
            "breachesClause15_2": (
                amendment_rate is not None and amendment_rate > AMENDMENT_RATE_CEILING
            ),
        },
        "verdicts": dict(Counter(r.get("verdict") for r in engine).most_common()),
        "amendedTo": dict(Counter(r.get("verdict") for r in human if
                                  r.get("humanOutcome") == "amended").most_common()),
        "latency": {
            "avgMs": avg_latency,
            "humanBaselineSeconds": HUMAN_BASELINE_SECONDS,
            "adjudicatorMinutesSaved": (
                round(auto * HUMAN_BASELINE_SECONDS / 60, 1) if total else None
            ),
        },
    }
