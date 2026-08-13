"""Clause chunking and retrieval behaviour."""
from __future__ import annotations

import pytest

from adjudicator import retrieval


@pytest.fixture(scope="module")
def retriever():
    return retrieval.get_retriever()


def test_chunks_are_clauses_not_token_windows(retriever):
    ids = {c.clause_id for c in retriever.clauses}
    # section-level, clause-level and sub-clause-level chunks all exist
    for expected in ("1.6", "2.3", "4.1", "5.1.1", "5.2.1", "5.5.3", "11.1", "12.3", "17", "18.2"):
        assert expected in ids, f"clause {expected} was not chunked"
    assert len(retriever.clauses) > 60


def test_each_chunk_carries_its_section_heading(retriever):
    clause = retriever.get("Clause 5.1.1")
    assert clause is not None
    assert "Reason Codes" in clause.section
    assert "photographic or video evidence" in clause.text


def test_lettered_sub_items_are_kept_with_their_parent(retriever):
    clause = retriever.get("Clause 4.1")
    assert clause is not None
    assert clause.letters == {"a", "b", "c", "d", "e"}
    assert "clearance discount of 60%" in clause.text


def test_inline_lettered_sub_items_are_found_too(retriever):
    """Clauses 5.1.1 and 11.1 carry (a)/(b) inline, not on their own line."""
    assert retriever.get("Clause 11.1").letters == {"a", "b"}
    assert retriever.get("Clause 5.1.1").letters == {"a", "b"}
    assert retriever.exists("Clause 11.1(a)")
    assert retriever.exists("Clause 5.1.1(b)")


def test_cross_references_do_not_become_own_letters(retriever):
    """Clause 11.1 points at 'Clause 4.1(e)' — that (e) belongs to 4.1, not 11.1."""
    assert "e" not in retriever.get("Clause 11.1").letters
    assert not retriever.exists("Clause 11.1(e)")


def test_citation_validation_checks_the_letter_too(retriever):
    assert retriever.exists("Clause 4.1(e)")
    assert not retriever.exists("Clause 4.1(z)")
    assert not retriever.exists("Clause 4.7")
    assert retriever.exists("Clause 12.3(a)")


def test_section_level_citations_resolve_but_do_not_rank(retriever):
    """'Clause 2 (category windows)' is citable; a title-only stub never ranks."""
    section = retriever.get("Clause 2")
    assert section is not None and section.title_only
    assert retriever.exists("Clause 2")
    assert section not in [c for c, _ in retriever.search("return window category days", 20)]


def test_internal_clauses_are_flagged(retriever):
    assert retriever.get("Clause 12.3").internal is True
    assert retriever.get("Clause 2.3").internal is False


def test_controlled_verdict_list_is_citable(retriever):
    clause = retriever.get("Clause 17")
    assert clause is not None
    assert "APPROVE_ON_PICKUP" in clause.text
    assert "CLOSE_PICKUP_FAILED" in clause.text


def test_query_is_built_from_structured_fields_only():
    query = retrieval.build_query(
        category="appliance",
        reason_code="DEFECT",
        payment_mode="PREPAID",
        days_since_delivery=6,
        flags={"clearance": False, "festivalSale": False, "fragile": False},
    )
    assert "appliance" in query and "DEFECT" in query and "day 6" in query
    # nothing free-text leaks into the primary query
    assert "stopped working" not in query


def test_search_surfaces_the_governing_clause(retriever):
    query = retrieval.build_query(
        category="appliance",
        reason_code="DEFECT",
        payment_mode="PREPAID",
        days_since_delivery=6,
        flags={},
    )
    top_ids = [c.clause_id for c, _ in retriever.search(query, top_k=8)]
    assert any(cid.startswith(("5.1", "2.1")) for cid in top_ids), top_ids


def test_keep_filter_drops_irrelevant_specialisations(retriever):
    exchange = retriever.get("Clause 10.2")   # advance exchange, apparel-oriented
    assert exchange is not None
    assert not retrieval.keep(exchange, category="personal_care", reason_code="CHANGE_OF_MIND")
