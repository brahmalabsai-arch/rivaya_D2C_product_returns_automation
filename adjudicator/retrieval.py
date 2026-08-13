"""Clause-level chunking + retrieval over RHL-POL-RET-3.2.

Design decisions (locked in IMPLEMENTATION_PLAN.md §4):

1. Chunk by clause, never by token count. Each chunk is one clause with its
   section heading attached, and the clause number lives in metadata. Citations
   are read off metadata — they are never generated, so a cited clause number
   always exists in the document.
2. The retrieval query is built server-side from *structured* payload fields.
   Free-text description is a secondary query only. Nothing an LLM writes ever
   becomes a retrieval query.
3. Lexical BM25 is the v1 ranker: it is deterministic, dependency-free and
   auditable, which matters more here than recall. `Retriever` exposes a
   pluggable `rerank` hook so an embedding model can be layered on later
   without touching callers.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import config

# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #

_H_RE = re.compile(r"^(#{1,3})\s+(.*?)\s*$")
_SECTION_NUM_RE = re.compile(r"^(\d+)\.\s+(.*)$")
# **2.1** Kitchen & Small Appliances ...
_BOLD_NUM_RE = re.compile(r"^\*\*(\d+(?:\.\d+)*)\*\*\s*(.*)$")
# **5.1 Kitchen & Small Appliances.**  (bold number *and* title)
_BOLD_TITLED_RE = re.compile(r"^\*\*(\d+(?:\.\d+)*)\s+([^*]*?)\*\*\s*(.*)$")
#   5.1.1 DEFECT claims within 10 days ...   (indented sub-clause, no bold)
_SUB_RE = re.compile(r"^\s+(\d+(?:\.\d+){1,})\s+(.*)$")
# Lettered sub-items belonging to a clause. They appear two ways in this
# document: on their own line (Clause 4.1, 12.3) and inline within the sentence
# (Clause 5.1.1 "(a) a description of the failure; (b) photographic evidence").
# Both must be discoverable or a citation like "Clause 11.1(a)" fails validation.
_LETTER_RE = re.compile(r"\(([a-z])\)")
# ...but a cross-reference to *another* clause's sub-item is not our own letter.
_CROSSREF_RE = re.compile(r"Clause\s+\d+(?:\.\d+)*\([a-z]\)")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Clause:
    """One adjudicable unit of policy."""

    clause_id: str          # "5.1.1", "12.3", "17"
    section: str            # "5. Reason Codes, Evidence Requirements, ..."
    title: str              # short label if the clause carried one
    text: str               # clause body, letters included
    internal: bool          # Clauses 12-18 are internal SOP (Clause 15.3)
    letters: set[str] = field(default_factory=set)
    # True for a section that has no prose of its own (e.g. "Clause 2", whose
    # body lives entirely in 2.1-2.6). Citable — "Clause 2 (category windows)"
    # is a legitimate citation — but excluded from ranking so a one-line stub
    # cannot outrank a real clause on BM25 length normalisation.
    title_only: bool = False
    _tokens: list[str] = field(default_factory=list, repr=False)

    @property
    def citation(self) -> str:
        return f"Clause {self.clause_id}"

    @property
    def searchable(self) -> str:
        return f"{self.section} {self.title} {self.text}"

    def as_dict(self) -> dict[str, str]:
        return {
            "clause": self.citation,
            "section": self.section,
            "text": self.text.strip(),
        }


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def parse_policy(path: Path) -> list[Clause]:
    """Split the markdown policy into clause chunks.

    Splits on the `**N.N**` / `N.N.N` markers. Section headings become their own
    chunk (clause_id = the section number) so that section-level citations such
    as "Clause 17" — the controlled verdict list, which has no numbered
    sub-clauses — remain citable.
    """
    lines = path.read_text(encoding="utf-8").splitlines()

    clauses: list[Clause] = []
    section = ""
    section_num: str | None = None
    internal = False
    current: Clause | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        if not current.text.strip():
            # Section headings stay citable even when the section is nothing but
            # its numbered clauses; anything else with no body is dropped.
            if "." in current.clause_id or not current.title:
                current = None
                return
            current.text = current.title
            current.title_only = True
        current.letters = _own_letters(current.text)
        current._tokens = _tokenize(current.searchable)
        clauses.append(current)
        current = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue

        h = _H_RE.match(line)
        if h:
            flush()
            heading = h.group(2).strip()
            if "INTERNAL SOP" in heading.upper():
                internal = True
            m = _SECTION_NUM_RE.match(heading)
            if m:
                section = heading
                section_num = m.group(1)
                # A section-level chunk collects any prose that appears before
                # the first numbered clause (e.g. Clause 17's verdict list).
                current = Clause(
                    clause_id=section_num,
                    section=section,
                    title=m.group(2),
                    text="",
                    internal=internal or int(section_num) >= 12,
                )
            else:
                section = heading
                section_num = None
            continue

        if line.startswith(">"):  # document note / blockquote
            continue
        if line.startswith("—"):  # "— End of Document —"
            continue

        titled = _BOLD_TITLED_RE.match(line)
        numbered = _BOLD_NUM_RE.match(line)
        sub = _SUB_RE.match(line)

        if titled and not numbered:
            flush()
            cid = titled.group(1)
            current = Clause(
                clause_id=cid,
                section=section,
                title=titled.group(2).strip(" ."),
                text=titled.group(3).strip(),
                internal=_is_internal(cid, internal),
            )
            continue

        if numbered:
            flush()
            cid = numbered.group(1)
            current = Clause(
                clause_id=cid,
                section=section,
                title="",
                text=numbered.group(2).strip(),
                internal=_is_internal(cid, internal),
            )
            continue

        if sub:
            flush()
            cid = sub.group(1)
            current = Clause(
                clause_id=cid,
                section=section,
                title="",
                text=sub.group(2).strip(),
                internal=_is_internal(cid, internal),
            )
            continue

        # continuation line — belongs to the clause above (lettered items,
        # wrapped sentences, the verdict list under a section heading)
        if current is not None:
            current.text = f"{current.text}\n{line.strip()}".strip()

    flush()
    return clauses


def _own_letters(text: str) -> set[str]:
    """The (a)/(b)/(c) sub-items this clause defines, excluding cross-references
    to another clause's sub-items (e.g. Clause 11.1 pointing at Clause 4.1(e))."""
    return set(_LETTER_RE.findall(_CROSSREF_RE.sub("", text)))


def _is_internal(clause_id: str, in_internal_part: bool) -> bool:
    try:
        return in_internal_part or int(clause_id.split(".")[0]) >= 12
    except ValueError:
        return in_internal_part


# --------------------------------------------------------------------------- #
# BM25
# --------------------------------------------------------------------------- #

_K1 = 1.4
_B = 0.75


class Retriever:
    """Deterministic clause retrieval: BM25 + structured-field keep-filter."""

    def __init__(self, clauses: list[Clause]):
        self.clauses = clauses
        self.by_id = {c.clause_id: c for c in clauses}
        # Only clauses with prose of their own take part in ranking.
        self._rankable = [c for c in clauses if not c.title_only]
        self._df: dict[str, int] = {}
        for c in self._rankable:
            for term in set(c._tokens):
                self._df[term] = self._df.get(term, 0) + 1
        self._n = max(len(self._rankable), 1)
        self._avg_len = sum(len(c._tokens) for c in self._rankable) / self._n

    # -- direct lookup (citations are resolved, never generated) ------------- #

    def get(self, citation: str) -> Clause | None:
        """Resolve 'Clause 5.1.1' / '4.1(e)' / '12.3(a)' to its chunk."""
        cid = normalise_clause_id(citation)
        return self.by_id.get(cid)

    def exists(self, citation: str) -> bool:
        """True when the clause number — and any (x) sub-item — is in the doc."""
        clause = self.get(citation)
        if clause is None:
            return False
        m = re.search(r"\(([a-z])\)\s*$", citation.strip())
        if m:
            return m.group(1) in clause.letters
        return True

    def resolve_all(self, citations: list[str]) -> list[Clause]:
        out: list[Clause] = []
        seen: set[str] = set()
        for cite in citations:
            clause = self.get(cite)
            if clause and clause.clause_id not in seen:
                seen.add(clause.clause_id)
                out.append(clause)
        return out

    # -- search -------------------------------------------------------------- #

    def _score(self, query_tokens: list[str], clause: Clause) -> float:
        if not clause._tokens:
            return 0.0
        length = len(clause._tokens)
        freqs: dict[str, int] = {}
        for t in clause._tokens:
            freqs[t] = freqs.get(t, 0) + 1
        score = 0.0
        for term in query_tokens:
            f = freqs.get(term, 0)
            if not f:
                continue
            df = self._df.get(term, 0)
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            denom = f + _K1 * (1 - _B + _B * length / self._avg_len)
            score += idf * (f * (_K1 + 1)) / denom
        return score

    def search(self, query: str, top_k: int | None = None) -> list[tuple[Clause, float]]:
        tokens = _tokenize(query)
        scored = [(c, self._score(tokens, c)) for c in self._rankable]
        scored = [(c, s) for c, s in scored if s > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[: (top_k or config.TOP_K)]


# --------------------------------------------------------------------------- #
# Query construction — structured fields only
# --------------------------------------------------------------------------- #

CATEGORY_KEYWORDS = {
    "appliance": "kitchen small appliances mixer grinder kettle appliance",
    "decor": "home decor ceramics vase lamp glassware fragile handcrafted",
    "apparel": "apparel soft furnishings kurta bedsheet cushion tags size fit",
    "personal_care": "personal care essential oil hygiene seal unopened",
}

REASON_KEYWORDS = {
    "DEFECT": "defect functional failure manufacturing evidence warranty",
    "DAMAGE_TRANSIT": "damage transit packaging photos logistics partner",
    "WRONG_ITEM": "wrong item different sku mismatch pick list replacement",
    "MISSING_PARTS": "missing parts accessories components package contents",
    "NOT_AS_DESCRIBED": "not as described colour variance product page spec mismatch",
    "SIZE_FIT": "size fit tags exchange apparel trial condition",
    "CHANGE_OF_MIND": "change of mind unused sealed reverse logistics fee",
    "LATE_DELIVERY_REFUSED": "late delivery promised date refused",
}


def build_query(
    *,
    category: str,
    reason_code: str,
    payment_mode: str,
    days_since_delivery: int,
    flags: dict[str, bool],
) -> str:
    """The primary retrieval query — templated from structured fields only."""
    active = " ".join(k for k, v in flags.items() if v)
    return (
        f"{category} {CATEGORY_KEYWORDS.get(category, '')} "
        f"{reason_code} {REASON_KEYWORDS.get(reason_code, '')} return, "
        f"{payment_mode} payment, day {days_since_delivery} return window, "
        f"flags: {active or 'none'}"
    )


def keep(clause: Clause, *, category: str, reason_code: str) -> bool:
    """Post-filter: keep clauses that mention the reason code, the category, or
    that belong to a general section (1-4, 7, 9, 12, 16-18)."""
    text = clause.searchable.lower()
    if reason_code and reason_code.lower() in text:
        return True
    for word in CATEGORY_KEYWORDS.get(category, "").split():
        if len(word) > 4 and word in text:
            return True
    root = clause.clause_id.split(".")[0]
    return root in {"1", "2", "3", "4", "7", "9", "12", "16", "17", "18"}


def normalise_clause_id(citation: str) -> str:
    """'Clause 12.3(a)' -> '12.3'; '5.1.1' -> '5.1.1'."""
    m = re.search(r"(\d+(?:\.\d+)*)", citation)
    return m.group(1) if m else citation.strip()


# --------------------------------------------------------------------------- #
# Module-level singleton (the policy doc is static per process)
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever(parse_policy(config.POLICY_PATH))
