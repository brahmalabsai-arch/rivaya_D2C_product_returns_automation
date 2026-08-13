"""Runtime configuration. Everything is env-overridable so n8n / Docker can
point the service at a different policy file or decision log without a rebuild.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

POLICY_PATH = Path(
    os.getenv("RIVAYA_POLICY_PATH", BASE_DIR / "policy" / "rivaya_returns_policy.md")
)
POLICY_VERSION = os.getenv("RIVAYA_POLICY_VERSION", "RHL-POL-RET-3.2")

DECISION_LOG_PATH = Path(
    os.getenv("RIVAYA_DECISION_LOG", BASE_DIR / "logs" / "decisions.jsonl")
)

# --- LLM (narrow roles only: description/reason sanity check + email drafting) ---
# The service is fully functional without an API key: both roles fall back to
# deterministic implementations. The LLM never selects a verdict.
LLM_MODEL = os.getenv("RIVAYA_LLM_MODEL", "claude-opus-5")
LLM_ENABLED = bool(os.getenv("ANTHROPIC_API_KEY")) and os.getenv("RIVAYA_USE_LLM", "1") != "0"

# --- retrieval ---
TOP_K = int(os.getenv("RIVAYA_TOP_K", "6"))

# --- thresholds mirrored from the policy (single source of truth: the doc) ---
HIGH_VALUE_THRESHOLD = 7500          # Clause 1.6
COD_CHANGE_OF_MIND_THRESHOLD = 3000  # Clause 6.3
LOYALTY_FEE_WAIVER_LTV = 50000       # Clause 7.4
