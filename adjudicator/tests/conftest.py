"""Test harness setup.

The suite runs with the LLM disabled so that results are reproducible and the
tests assert the *deterministic* layer — which is the layer that decides. The
LLM path is exercised separately by test_llm_fallback.py.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Must be set before `adjudicator.config` is imported.
os.environ["RIVAYA_USE_LLM"] = "0"
os.environ.setdefault(
    "RIVAYA_DECISION_LOG",
    str(Path(tempfile.gettempdir()) / "rivaya-test-decisions.jsonl"),
)

import pytest  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def fixtures() -> dict[str, dict]:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in FIXTURE_DIR.glob("*.json")}


@pytest.fixture(autouse=True)
def _clean_log():
    """Each test writes to a fresh decision log so tail() assertions are exact."""
    path = Path(os.environ["RIVAYA_DECISION_LOG"])
    if path.exists():
        path.unlink()
    yield
