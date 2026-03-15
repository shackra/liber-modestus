"""Main document resolver: evaluates conditions, resolves cross-references,
and filters display markers to produce a clean Document for presentation.

Processing order (matches the Perl pipeline):

1. Evaluate section-level rubric conditions on ``[Section] (condition)``
   headers — keep only the correct variant for each section name.
2. Resolve preamble-level ``@`` includes (whole-file defaults).
3. Resolve section-level ``@`` includes (iteratively, max 7 deep).
4. Process inline conditionals (``(sed ...)``, ``(vero ...)``, etc.)
   with backward/forward scoping.
5. Filter display markers (``!*S``, ``!*R``, ``!*D``, etc.) based on
   the Mass type.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from captator.parser import parse as parse_text
from captator.parser import parse_file
from captator.parser.ast_nodes import (
    ConditionalLine,
    CrossRef,
    Document,
    Line,
    LineKind,
    RubricCondition,
    ScriptureRef,
    Section,
    SectionHeader,
    TextLine,
)

from .config import MassType, MissalConfig
from .evaluator import vero

# Maximum depth for iterative @-reference resolution within a section.
_MAX_REF_DEPTH = 7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve(
    doc: Document,
    config: MissalConfig,
    base_path: str | Path,
) -> Document:
    """Resolve a parsed Document according to the missal configuration.

    Args:
        doc: A ``Document`` AST from the parser.
        config: The missal configuration (rubric, mass type, etc.).
        base_path: Base directory for resolving ``@`` file references
            (e.g., ``".../web/www/missa/Latin"``).

    Returns:
        A new ``Document`` with conditions evaluated, cross-references
        resolved, and display markers filtered.
    """
    base = Path(base_path)

    # Phase 1: Evaluate section-level rubric conditions.
    sections = _select_section_variants(doc.sections, config)

    # Phase 2: Resolve preamble-level @ includes (whole-file defaults).
    preamble, sections = _resolve_preamble_includes(
        doc.preamble, sections, config, base
    )

    # Phase 3: Resolve section-level @ includes (iterative).
    sections = [_resolve_section_refs(s, config, base) for s in sections]

    # Phase 4: Process inline conditionals within each section body.
    sections = [_process_section_conditionals(s, config) for s in sections]

    # Phase 5: Filter display markers based on Mass type.
    preamble = _filter_display_markers(preamble, config)
    sections = [
        Section(header=s.header, body=_filter_display_markers(s.body, config))
        for s in sections
    ]

    # Phase 6: Remove empty sections.
    sections = [s for s in sections if s.body]

    return Document(preamble=preamble, sections=sections)


# ---------------------------------------------------------------------------
# Phase 1: Section variant selection
# ---------------------------------------------------------------------------


def _select_section_variants(
    sections: list[Section], config: MissalConfig
) -> list[Section]:
    """For each section name, select the correct rubric variant.

    When multiple ``[SectionName]`` and ``[SectionName] (condition)``
    exist, we keep:
    - The unconditional section (no rubric) as the default.
    - If a conditional section's rubric matches, it replaces the default.

    For inline conditionals within ``[Rank]`` (e.g., multiple rank values
    with ``(sed rubrica ...)`` between them), these are handled in Phase 4.
    We keep the section as-is and let conditional processing handle it.
    """
    result: list[Section] = []
    # Track which section names we've already resolved
    seen_names: dict[str, int] = {}

    for section in sections:
        name = section.header.name

        if section.header.rubric is not None:
            # Conditional section: evaluate the condition
            condition_met = vero(section.header.rubric.expression, config)

            if name in seen_names:
                # We already have a version of this section
                if condition_met:
                    # This conditional version wins — replace the existing one
                    result[seen_names[name]] = Section(
                        header=SectionHeader(
                            kind=LineKind.SECTION_HEADER,
                            raw=section.header.raw,
                            line_number=section.header.line_number,
                            name=name,
                            rubric=None,  # Clear the condition (it was satisfied)
                        ),
                        body=section.body,
                    )
            else:
                # First occurrence of this section name, and it's conditional
                if condition_met:
                    idx = len(result)
                    seen_names[name] = idx
                    result.append(
                        Section(
                            header=SectionHeader(
                                kind=LineKind.SECTION_HEADER,
                                raw=section.header.raw,
                                line_number=section.header.line_number,
                                name=name,
                                rubric=None,
                            ),
                            body=section.body,
                        )
                    )
                # If not met, skip entirely (no default exists)
        else:
            # Unconditional section
            if name in seen_names:
                # Duplicate unconditional section — shouldn't happen normally,
                # but keep the first one
                pass
            else:
                idx = len(result)
                seen_names[name] = idx
                result.append(section)

    return result


# ---------------------------------------------------------------------------
# Phase 2: Preamble-level @ includes
# ---------------------------------------------------------------------------


def _resolve_preamble_includes(
    preamble: list[Line],
    sections: list[Section],
    config: MissalConfig,
    base: Path,
) -> tuple[list[Line], list[Section]]:
    """Resolve preamble-level @-references (whole-file defaults).

    A preamble ``@File`` means: load all sections from that file and use
    them as defaults for any sections not already defined.
    """
    new_preamble: list[Line] = []
    existing_names = {s.header.name for s in sections}

    for line in preamble:
        if isinstance(line, CrossRef) and line.file_ref:
            # Load the referenced file
            ref_doc = _load_referenced_file(line.file_ref, None, base)
            if ref_doc:
                # Add missing sections as defaults
                for ref_section in ref_doc.sections:
                    if ref_section.header.name not in existing_names:
                        sections.append(ref_section)
                        existing_names.add(ref_section.header.name)
        else:
            new_preamble.append(line)

    return new_preamble, sections


# ---------------------------------------------------------------------------
# Phase 3: Section-level @ resolution
# ---------------------------------------------------------------------------


def _resolve_section_refs(
    section: Section,
    config: MissalConfig,
    base: Path,
) -> Section:
    """Resolve @-references within a section body (iteratively, max 7 deep)."""
    body = list(section.body)

    for _iteration in range(_MAX_REF_DEPTH):
        new_body: list[Line] = []
        had_refs = False

        for line in body:
            if isinstance(line, CrossRef):
                had_refs = True
                resolved_lines = _resolve_single_ref(
                    line, section.header.name, config, base
                )
                new_body.extend(resolved_lines)
            else:
                new_body.append(line)

        body = new_body
        if not had_refs:
            break

    return Section(header=section.header, body=body)


def _resolve_single_ref(
    ref: CrossRef,
    current_section_name: str,
    config: MissalConfig,
    base: Path,
) -> list[Line]:
    """Resolve a single @-reference to its content lines.

    Returns the replacement lines, or the original ref line if resolution
    fails (so the user can see what couldn't be resolved).
    """
    target_section = ref.section_ref or current_section_name

    if ref.is_self_ref:
        # Self-reference: we can't resolve without the full document context.
        # For now, keep it as-is (a future pass could handle this).
        return [ref]

    if not ref.file_ref:
        return [ref]

    ref_doc = _load_referenced_file(ref.file_ref, target_section, base)
    if ref_doc is None:
        # File not found — keep the reference as-is
        return [ref]

    # Find the target section
    target = ref_doc.get_section(target_section)
    if target is None:
        # Section not found — if no specific section was requested,
        # this might be a whole-file reference. Return preamble content.
        if ref.section_ref is None and ref_doc.preamble:
            lines = list(ref_doc.preamble)
        else:
            return [ref]
    else:
        lines = list(target.body)

    # Apply substitutions if present
    if ref.substitutions:
        lines = _apply_substitutions(lines, ref.substitutions)

    return lines


def _load_referenced_file(
    file_ref: str,
    section_name: Optional[str],
    base: Path,
) -> Optional[Document]:
    """Load and parse a referenced file.

    Handles path construction: ``Tempora/Nat2-0`` -> ``base/Tempora/Nat2-0.txt``.
    """
    # Normalize the file reference
    ref_path = file_ref.strip()

    # Add .txt extension if not present
    if not ref_path.endswith(".txt"):
        ref_path += ".txt"

    full_path = base / ref_path

    if not full_path.is_file():
        # Try without Commune/ prefix redirect (missa communes may
        # reference horas commons — we stay within our base for now)
        return None

    try:
        return parse_file(str(full_path))
    except Exception:
        return None


def _apply_substitutions(lines: list[Line], subs: str) -> list[Line]:
    """Apply substitution operations to a list of lines.

    Supports:
    - Line selection: ``3`` (line 3), ``1-4`` (lines 1-4),
      ``!3`` (all except line 3)
    - Regex: ``s/pattern/replacement/flags``
    """
    # Parse substitution operations
    remaining = subs.strip()

    # Process each substitution operation
    for m in re.finditer(
        r"(?:s/(?P<s>[^/]*)/(?P<r>[^/]*)/(?P<f>[gism]*))"
        r"|(?:(?P<n>!?)(?P<b>\d+)(?:-(?P<e>\d+))?)",
        remaining,
    ):
        if m.group("b"):
            # Line selection
            start = int(m.group("b")) - 1  # 0-indexed
            end = int(m.group("e")) if m.group("e") else start + 1
            negate = bool(m.group("n"))

            if negate:
                # Keep everything EXCEPT the selected range
                lines = lines[:start] + lines[end:]
            else:
                # Keep ONLY the selected range
                lines = lines[start:end]
        elif m.group("s") is not None:
            # Regex substitution on the raw text of each line
            pattern = m.group("s")
            replacement = m.group("r")
            flags_str = m.group("f") or ""

            re_flags = 0
            count = 1
            if "g" in flags_str:
                count = 0  # replace all
            if "i" in flags_str:
                re_flags |= re.IGNORECASE
            if "m" in flags_str:
                re_flags |= re.MULTILINE
            if "s" in flags_str:
                re_flags |= re.DOTALL

            new_lines: list[Line] = []
            for line in lines:
                new_raw = re.sub(
                    pattern, replacement, line.raw, count=count, flags=re_flags
                )
                if new_raw != line.raw:
                    # Create a new TextLine with the modified content
                    new_lines.append(
                        TextLine(
                            kind=LineKind.TEXT,
                            raw=new_raw,
                            line_number=line.line_number,
                            body=new_raw.strip(),
                        )
                    )
                else:
                    new_lines.append(line)
            lines = new_lines

    return lines


# ---------------------------------------------------------------------------
# Phase 4: Inline conditional processing
# ---------------------------------------------------------------------------

# Regex for inline conditionals: (stopwords condition scope_keywords)
_RE_CONDITIONAL_CONTENT = re.compile(
    r"^\s*"
    r"(?:(?P<stopwords>(?:(?:sed|vero|atque|attamen|si|deinde)\s*)+))?"
    r"(?P<condition>.*?)"
    r"(?:\s+(?P<scope>dicitur|dicuntur|omittitur|omittuntur|semper"
    r"|loco\s+hujus\s+versus|loco\s+horum\s+versuum))?"
    r"\s*$",
    re.IGNORECASE,
)

# Stopwords that have implicit backscope (can remove preceding lines)
_BACKSCOPED_STOPWORDS = {"sed", "vero", "atque", "attamen"}

# Stopword strength weights
_STOPWORD_WEIGHTS = {
    "si": 0,
    "sed": 1,
    "vero": 1,
    "deinde": 1,
    "atque": 2,
    "attamen": 3,
}


def _process_section_conditionals(section: Section, config: MissalConfig) -> Section:
    """Process inline conditionals within a section body.

    This implements the backward/forward scoping logic from the Perl
    ``process_conditional_lines()`` function, simplified for the AST-based
    approach.
    """
    output: list[Line] = []

    i = 0
    body = section.body
    while i < len(body):
        line = body[i]

        if isinstance(line, ConditionalLine):
            condition_text = line.condition.expression
            parsed = _parse_inline_conditional(condition_text)

            condition_met = vero(parsed["condition"], config)
            has_backscope = parsed["has_backscope"]
            is_omission = parsed["is_omission"]

            if condition_met:
                if is_omission and has_backscope:
                    # Remove preceding content (backward scope)
                    _backscope_remove(output, parsed["backscope_level"])
                    i += 1
                    continue
                elif has_backscope and not is_omission:
                    # Replace preceding content: remove it, then include
                    # the following line(s)
                    _backscope_remove(output, parsed["backscope_level"])
                    # The next lines are the replacement — they'll be added
                    # normally in subsequent iterations
                    i += 1
                    continue
                else:
                    # Forward-only: following lines are included (default behavior)
                    i += 1
                    continue
            else:
                if is_omission:
                    # Condition not met for omission -> keep preceding content
                    i += 1
                    continue
                elif has_backscope:
                    # Condition not met: skip the conditional AND the
                    # following replacement lines (forward scope)
                    i += 1
                    # Skip lines until the next blank-ish line or another conditional
                    scope = parsed["forward_scope"]
                    if scope == "line":
                        # Skip exactly one following line
                        if i < len(body) and not isinstance(body[i], ConditionalLine):
                            i += 1
                    elif scope == "chunk":
                        # Skip until next blank line (which we represent as
                        # a break in the token stream — but our lexer skips blanks).
                        # In practice, skip until next conditional or different pattern.
                        pass
                    continue
                else:
                    # No backscope, condition not met: skip following content
                    i += 1
                    scope = parsed["forward_scope"]
                    if scope == "line":
                        if i < len(body) and not isinstance(body[i], ConditionalLine):
                            i += 1
                    continue
        else:
            output.append(line)
            i += 1

    return Section(header=section.header, body=output)


def _parse_inline_conditional(condition_text: str) -> dict:
    """Parse an inline conditional expression into its components."""
    m = _RE_CONDITIONAL_CONTENT.match(condition_text)

    result = {
        "condition": "",
        "has_backscope": False,
        "is_omission": False,
        "backscope_level": "line",
        "forward_scope": "line",
        "strength": 0,
    }

    if not m:
        result["condition"] = condition_text
        return result

    stopwords_str = (m.group("stopwords") or "").strip()
    condition = (m.group("condition") or "").strip()
    scope_kw = (m.group("scope") or "").strip().lower()

    result["condition"] = condition

    # Parse stopwords
    stopwords = re.findall(
        r"\b(sed|vero|atque|attamen|si|deinde)\b", stopwords_str, re.IGNORECASE
    )
    strength = sum(_STOPWORD_WEIGHTS.get(sw.lower(), 0) for sw in stopwords)
    has_backscope = any(sw.lower() in _BACKSCOPED_STOPWORDS for sw in stopwords)

    result["strength"] = strength
    result["has_backscope"] = has_backscope

    # Parse scope keywords
    if "omittitur" in scope_kw or "omittuntur" in scope_kw:
        result["is_omission"] = True
        if "omittuntur" in scope_kw or "versuum" in scope_kw:
            result["backscope_level"] = "nest"
        else:
            result["backscope_level"] = "chunk"
    elif "versuum" in scope_kw:
        result["backscope_level"] = "nest"
    elif "versus" in scope_kw:
        result["backscope_level"] = "chunk"

    # Forward scope
    if result["is_omission"]:
        result["forward_scope"] = "none"
    elif "dicuntur" in scope_kw:
        result["forward_scope"] = "chunk"
    elif "dicitur" in scope_kw:
        result["forward_scope"] = "line"
    else:
        result["forward_scope"] = "line"

    return result


def _backscope_remove(output: list[Line], level: str) -> None:
    """Remove preceding lines from the output according to backscope level."""
    if not output:
        return

    if level == "line":
        # Remove just the last line
        output.pop()
    elif level == "chunk":
        # Remove trailing non-blank lines (our lines are never truly blank
        # since the lexer skips them, so we remove trailing non-conditional lines)
        while output and not isinstance(output[-1], ConditionalLine):
            output.pop()
            if not output:
                break
    elif level == "nest":
        # More aggressive: remove back to the last "fence" (conditional boundary).
        # For simplicity, remove all trailing non-conditional lines.
        while output and not isinstance(output[-1], ConditionalLine):
            output.pop()
            if not output:
                break


# ---------------------------------------------------------------------------
# Phase 5: Display marker filtering
# ---------------------------------------------------------------------------


def _filter_display_markers(lines: list[Line], config: MissalConfig) -> list[Line]:
    """Filter lines based on ``!*S``/``!*R``/``!*D``/``!*nD`` display markers.

    Display markers affect all following lines until the next marker or
    section break.
    """
    output: list[Line] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if (
            isinstance(line, ScriptureRef)
            and line.is_display_marker
            and line.display_marker
        ):
            marker = line.display_marker

            skip = _should_skip_marker(marker, config)

            if skip:
                # Skip this marker AND all following lines until we hit
                # another display marker, a section break, or end of body
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    # Stop at the next display marker
                    if (
                        isinstance(next_line, ScriptureRef)
                        and next_line.is_display_marker
                        and next_line.display_marker
                    ):
                        break
                    # Stop at headings (structural breaks in Ordo)
                    if next_line.kind == LineKind.HEADING:
                        break
                    i += 1
                continue
            else:
                # Marker passes: skip the marker line itself but show content
                i += 1
                continue
        else:
            output.append(line)
            i += 1

    return output


def _should_skip_marker(marker: str, config: MissalConfig) -> bool:
    """Determine if a display marker's content should be skipped."""
    skip = False

    # Check for function hooks: !*&funcname — skip for now (not evaluable)
    if marker.startswith("&"):
        return False

    # !*nD — NOT Defunctorum: skip if this IS a Requiem
    if "nD" in marker and config.is_requiem:
        skip = True

    # !*D — Defunctorum: skip if this is NOT a Requiem
    if "D" in marker and "nD" not in marker and not config.is_requiem:
        skip = True

    # !*S — Solemn: skip if NOT solemn
    if "S" in marker and "Sn" not in marker and not config.is_solemn:
        skip = True

    # !*R — Read: skip if solemn
    if "R" in marker and config.is_solemn:
        skip = True

    return skip
