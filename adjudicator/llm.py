"""The two narrow LLM roles, each with a deterministic fallback.

(a) Perception — does the free-text description actually describe the reason
    code the customer selected? A mismatch means the case was classified on a
    shaky basis, so it becomes AMBIGUOUS and goes to a person (Clause 18.2).
(b) Drafting — turn a decided verdict plus the cited clause texts into a
    customer email.

The LLM never selects a verdict, never chooses a lane, and never produces a
clause citation. If no API key is configured the service runs unchanged on the
keyword matcher and the templated drafts.
"""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from . import config

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# (a) reason / description alignment
# --------------------------------------------------------------------------- #

# Keyword signals per reason code. Deliberately conservative: a mismatch is only
# raised when the text clearly points at some *other* controlled reason code.
_REASON_SIGNALS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"stopp?ed working|not working|won'?t (start|turn|switch)|dead|"
                r"defect|faulty|malfunction|burning smell|sparks?|overheat", re.I), "DEFECT"),
    (re.compile(r"damag\w*|crack\w*|broke\w*|shatter\w*|dent\w*|torn box|smashed", re.I),
     "DAMAGE_TRANSIT"),
    (re.compile(r"wrong (item|product|colou?r sent)|different item|not what i ordered|"
                r"received .* instead", re.I), "WRONG_ITEM"),
    (re.compile(r"missing|not included|no (jar|accessor\w*|manual|part|lid|charger)", re.I),
     "MISSING_PARTS"),
    (re.compile(r"not as described|looks different|doesn'?t match the (product|page|photo)|"
                r"misleading|colou?r is (off|different)", re.I), "NOT_AS_DESCRIBED"),
    (re.compile(r"\bsize\b|\bfit\b|too (small|big|tight|loose|short|long)", re.I), "SIZE_FIT"),
    (re.compile(r"arrived (too )?late|delayed|after the promised", re.I), "LATE_DELIVERY_REFUSED"),
    (re.compile(r"changed my mind|don'?t (want|need)|no longer (want|need)|"
                r"bought by mistake|ordered by mistake", re.I), "CHANGE_OF_MIND"),
]

_MIN_WORDS_FOR_SIGNAL = 3


class _Alignment(BaseModel):
    """Structured output schema for the perception call."""

    aligned: bool = Field(description="True if the description is consistent with the reason code")
    detected_reason: str = Field(
        default="",
        description=(
            "The controlled reason code the description actually describes, or an empty string "
            "if it cannot be mapped to one of the eight controlled codes."
        ),
    )
    note: str = Field(default="", description="One short sentence explaining the judgement")


def check_alignment(description: str, reason_code: str) -> tuple[bool, str]:
    """Return (aligned, note). Never raises — a failed LLM call falls back."""
    text = (description or "").strip()
    if len(text.split()) < _MIN_WORDS_FOR_SIGNAL:
        return True, "Description too short to contradict the selected reason code."

    if config.LLM_ENABLED:
        try:
            return _check_alignment_llm(text, reason_code)
        except Exception as exc:  # noqa: BLE001 - degradation must never 500
            log.warning("alignment check fell back to keywords: %s", exc)

    return _check_alignment_keywords(text, reason_code)


def _check_alignment_keywords(text: str, reason_code: str) -> tuple[bool, str]:
    detected = {code for pattern, code in _REASON_SIGNALS if pattern.search(text)}
    if not detected:
        return True, "No competing reason-code signal found in the description."
    if reason_code in detected:
        return True, f"Description is consistent with {reason_code}."
    return False, (
        f"The description reads like a {'/'.join(sorted(detected))} claim, but the request is "
        f"filed as {reason_code}."
    )


def _check_alignment_llm(text: str, reason_code: str) -> tuple[bool, str]:
    import anthropic

    client = anthropic.Anthropic()
    prompt = (
        "You classify returns descriptions for a retailer's adjudication engine.\n"
        "The eight controlled reason codes are: DEFECT (functional/material failure), "
        "DAMAGE_TRANSIT (physical damage on arrival), WRONG_ITEM, MISSING_PARTS, "
        "NOT_AS_DESCRIBED (colour/material/spec mismatch), SIZE_FIT (apparel only), "
        "CHANGE_OF_MIND (no fault alleged), LATE_DELIVERY_REFUSED.\n\n"
        f"Selected reason code: {reason_code}\n"
        f"Customer description: {text!r}\n\n"
        "Decide whether the description is consistent with the selected code. Treat vague or "
        "brief descriptions as consistent — only report a mismatch when the description clearly "
        "describes a different controlled reason code. Fill detected_reason only from the eight "
        "codes above; leave it empty if nothing maps."
    )
    response = client.messages.parse(
        model=config.LLM_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
        output_format=_Alignment,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise RuntimeError("structured output did not parse")
    if parsed.aligned:
        return True, parsed.note or f"Description is consistent with {reason_code}."
    detected = parsed.detected_reason or "a different reason"
    return False, parsed.note or (
        f"The description reads like a {detected} claim, but the request is filed as {reason_code}."
    )


# --------------------------------------------------------------------------- #
# (b) customer email drafting
# --------------------------------------------------------------------------- #

_DRAFT_SYSTEM = (
    "You write customer emails for Rivaya Home & Living's returns desk.\n"
    "Rules you must follow exactly:\n"
    "- The decision is already made. Never change it, soften it, or hedge it.\n"
    "- Plain language, no legalese, no emoji. Six sentences at most in the body.\n"
    "- State the decision, the reason in plain words, the refund method and timeline if one "
    "applies, and the next physical step.\n"
    "- Offer exactly one recourse path — the one given to you, never both.\n"
    "- Do not invent clause numbers, amounts, dates or timelines. Use only what you are given.\n"
    "- End the body with the exact footer line you are given, on its own line.\n"
    "Return only the email body text. Do not include a subject line or a greeting placeholder."
)


def polish_email(*, subject: str, body: str, context: str) -> tuple[str, str]:
    """Optionally rewrite a templated draft. Returns (subject, body) unchanged on failure."""
    if not config.LLM_ENABLED:
        return subject, body
    try:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=2048,
            system=_DRAFT_SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"{context}\n\nTemplated draft:\n{body}"}],
        )
        if response.stop_reason == "refusal":
            return subject, body
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return (subject, text) if text else (subject, body)
    except Exception as exc:  # noqa: BLE001
        log.warning("email polish fell back to the template: %s", exc)
        return subject, body
