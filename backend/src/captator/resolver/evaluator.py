"""Rubric condition evaluator — Python equivalent of the Perl ``vero()``.

Evaluates Latin-language boolean expressions found in ``(rubrica ...)``
conditions.  The expression grammar is:

    expression  := disjunct ('aut' disjunct)*
    disjunct    := atom (('et' | 'nisi') atom)*
    atom        := [subject] predicate

Operator precedence: ``aut`` (OR) binds **tighter** than ``et`` (AND).
This matches the Perl implementation where the outer loop splits on
``aut`` and the inner loop splits on ``et``/``nisi``.

``nisi`` means "unless": once encountered in a disjunct, all subsequent
atoms in that branch must evaluate to **false** for the branch to succeed.
``nisi`` resets at each ``aut`` boundary.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import MissalConfig


# ---------------------------------------------------------------------------
# Known subjects: map keyword -> function(config) -> subject_value
# ---------------------------------------------------------------------------

_SUBJECTS: dict[str, str] = {
    "rubrica": "rubrica",
    "rubricis": "rubrica",
    "tempore": "tempore",
    "die": "die",
    "feria": "feria",
    "commune": "commune",
    "votiva": "votiva",
    "officio": "officio",
    "communi": "rubrica",  # alias in Perl
    "mense": "mense",
}


def _get_subject_value(subject_key: str, config: MissalConfig) -> str:
    """Return the runtime value for a subject key."""
    match subject_key:
        case "rubrica":
            return config.version_string
        case "tempore":
            return config.tempus_id
        case "die":
            return config.dayname
        case "feria":
            return str(config.day_of_week)
        case "commune":
            return config.commune
        case "votiva":
            return config.votive
        case "officio":
            return config.dayname
        case "mense":
            # In Perl, this is the month number as a string
            return ""  # Not used for missa resolution
        case _:
            return ""


# ---------------------------------------------------------------------------
# Known predicates: map keyword -> function(subject_value) -> bool
# ---------------------------------------------------------------------------

_PREDICATES: dict[str, re.Pattern[str]] = {
    "tridentina": re.compile(r"Trident", re.IGNORECASE),
    "monastica": re.compile(r"Monastic", re.IGNORECASE),
    "praedicatorum": re.compile(r"Praedicatorum|Ordo Praedicatorum", re.IGNORECASE),
    "cisterciensis": re.compile(r"Cisterciensis", re.IGNORECASE),
    "innovata": re.compile(r"2020 USA|NewCal", re.IGNORECASE),
    "innovatis": re.compile(r"2020 USA|NewCal", re.IGNORECASE),
    "paschali": re.compile(r"Paschæ|Ascensionis|Octava Pentecostes", re.IGNORECASE),
    "post septuagesimam": re.compile(r"Septua|Quadra|Passio", re.IGNORECASE),
    "feriali": re.compile(r"feria|vigilia", re.IGNORECASE),
    "summorum pontificum": re.compile(r"194[2-9]|195[45]|196", re.IGNORECASE),
}

# Numeric predicates (for feria subject: 1=Sunday, ..., 7=Saturday)
_NUMERIC_PREDICATES: dict[str, int] = {
    "prima": 1,
    "secunda": 2,
    "tertia": 3,
    "quarta": 4,
    "quinta": 5,
    "sexta": 6,
    "septima": 7,
    "longior": 1,
    "brevior": 2,
}


def _test_predicate(predicate_text: str, subject_value: str) -> bool:
    """Test a predicate against a subject value.

    Known predicates use their compiled regex/numeric test.
    Unknown predicates are treated as case-insensitive regexes
    matched against the subject value (replicating Perl behavior).
    """
    key = predicate_text.lower().strip()

    # Check known regex predicates
    if key in _PREDICATES:
        return bool(_PREDICATES[key].search(subject_value))

    # Check numeric predicates
    if key in _NUMERIC_PREDICATES:
        try:
            return int(subject_value) == _NUMERIC_PREDICATES[key]
        except (ValueError, TypeError):
            return False

    # Unknown predicate: treat as a regex against the subject value.
    # This is how conditions like "rubrica 1960", "rubrica 196",
    # "rubrica 1955", "die Epiphaniæ", "tempore Adventus" work.
    try:
        return bool(re.search(predicate_text, subject_value, re.IGNORECASE))
    except re.error:
        # If the predicate isn't valid regex, do literal substring match
        return predicate_text.lower() in subject_value.lower()


# ---------------------------------------------------------------------------
# The main vero() evaluator
# ---------------------------------------------------------------------------


def vero(condition: str, config: MissalConfig) -> bool:
    """Evaluate a rubric condition expression.

    Replicates the Perl ``vero()`` function from SetupString.pl.

    Args:
        condition: The condition string, e.g., ``"rubrica 1960"`` or
            ``"rubrica tridentina nisi rubrica cisterciensis"``.
        config: The missal configuration providing runtime values.

    Returns:
        True if the condition is satisfied under the given configuration.
    """
    condition = condition.strip()

    # Empty condition is TRUE (safe default per Perl implementation)
    if not condition:
        return True

    # Split on 'aut' (OR) — aut binds tighter, so it's the outer split
    for disjunct in re.split(r"\baut\b", condition):
        if _evaluate_disjunct(disjunct.strip(), config):
            return True

    return False


def _evaluate_disjunct(disjunct: str, config: MissalConfig) -> bool:
    """Evaluate a single disjunct (AND-chain with possible nisi negation)."""
    if not disjunct.strip():
        return True

    negation = False

    # Split on 'et' or 'nisi', capturing the separator
    parts = re.split(r"\b(et|nisi)\b", disjunct)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Handle separators
        if part == "nisi":
            negation = True
            continue
        if part == "et":
            continue

        # Evaluate the atomic condition
        result = _evaluate_atom(part, config)

        # Apply negation (xor): if negation is active, result must be False
        if result == negation:
            # This disjunct fails: result is True but we need False (negation),
            # or result is False but we need True (no negation).
            return False

    return True


def _evaluate_atom(atom: str, config: MissalConfig) -> bool:
    """Evaluate a single atomic condition like ``rubrica 1960``."""
    atom = atom.strip()
    if not atom:
        return True

    # Normalize whitespace
    atom = re.sub(r"\s+", " ", atom)

    # Try to split into subject + predicate
    parts = atom.split(None, 1)

    if len(parts) == 1:
        # Single word: could be just a predicate with implicit subject
        word = parts[0]
        if word.lower() in _SUBJECTS:
            # A bare subject with no predicate — treat as always true
            return True
        # It's a predicate with implicit 'tempore' subject
        subject_key = "tempore"
        predicate = word
    else:
        maybe_subject, maybe_predicate = parts[0], parts[1]

        if maybe_subject.lower() in _SUBJECTS:
            subject_key = _SUBJECTS[maybe_subject.lower()]
            predicate = maybe_predicate
        else:
            # First word is not a recognized subject: treat entire atom
            # as a predicate with implicit 'tempore' subject
            subject_key = "tempore"
            predicate = atom

    subject_value = _get_subject_value(subject_key, config)
    return _test_predicate(predicate, subject_value)
