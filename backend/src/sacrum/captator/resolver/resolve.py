"""Main document resolver: evaluates conditions, resolves cross-references,
expands macros/subroutines, and filters display markers to produce a clean
Document for presentation.

Processing order (matches the Perl pipeline):

1. Evaluate section-level rubric conditions on ``[Section] (condition)``
   headers — keep only the correct variant for each section name.
2. Resolve preamble-level ``@`` includes (whole-file defaults).
3. Resolve section-level ``@`` includes (iteratively, max 7 deep),
   including self-references (``@:SectionName``).
4. Process inline conditionals (``(sed ...)``, ``(vero ...)``, etc.)
   with backward/forward scoping.
5. Filter display markers (``!*S``, ``!*R``, ``!*D``, etc.) based on
   the Mass type.
6. Expand ``$`` macros (prayer conclusions from Prayers.txt).
7. Expand static ``&`` subroutines (``&Gloria``, ``&DominusVobiscum``,
   HTML entities).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..parser import parse as parse_text
from ..parser import parse_file
from ..parser.ast_nodes import (
    ConditionalLine,
    CrossRef,
    Document,
    GloriaRef,
    Line,
    LineKind,
    MacroRef,
    RubricCondition,
    ScriptureRef,
    Section,
    SectionHeader,
    SubroutineRef,
    TextLine,
)
from .config import MassType, MissalConfig
from .evaluator import vero

# Maximum depth for iterative @-reference resolution within a section.
_MAX_REF_DEPTH = 7

# HTML entities that &Name maps to (used in Holy Saturday texts).
_HTML_ENTITIES: dict[str, str] = {
    "Psi": "\u03a8",  # Ψ
    "Alpha": "\u0391",  # Α
    "Omega": "\u03a9",  # Ω
}


# ---------------------------------------------------------------------------
# Prayer/macro database loading
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _load_prayers_db(prayers_path: str) -> dict[str, list[Line]]:
    """Load and cache a Prayers.txt file as a section-name -> lines dict.

    Returns a mapping from prayer name (e.g., "Per Dominum") to the list
    of body lines for that section.
    """
    path = Path(prayers_path)
    if not path.is_file():
        return {}

    try:
        doc = parse_file(str(path))
    except Exception:
        return {}

    db: dict[str, list[Line]] = {}
    for section in doc.sections:
        db[section.header.name] = section.body
    return db


def _get_prayers_db(base: Path, language: str) -> dict[str, list[Line]]:
    """Get the prayers database with language layering.

    Latin is always the base layer.  If *language* is not ``"Latin"``,
    the translated Prayers.txt is loaded and its sections override the
    Latin ones.  Sections not present in the translation fall back to
    Latin automatically.

    The ``base`` path is expected to point at a specific language
    directory (e.g., ``…/missa/Latin``).  We derive the missa root
    from it to locate sibling language directories.
    """
    # Determine the missa root (parent of the language directory).
    missa_root = base.parent

    # 1. Always load Latin as the base layer.
    latin_path = missa_root / "Latin" / "Ordo" / "Prayers.txt"
    db = dict(_load_prayers_db(str(latin_path)))

    # 2. Overlay the requested language on top (if different from Latin).
    if language and language != "Latin":
        lang_path = missa_root / language / "Ordo" / "Prayers.txt"
        lang_db = _load_prayers_db(str(lang_path))
        db.update(lang_db)

    return db


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
        resolved, macros expanded, and display markers filtered.
    """
    base = Path(base_path)

    # Phase 1: Evaluate section-level rubric conditions.
    sections = _select_section_variants(doc.sections, config)

    # Phase 2: Resolve preamble-level @ includes (whole-file defaults).
    preamble, sections = _resolve_preamble_includes(
        doc.preamble, sections, config, base
    )

    # Phase 3: Process inline conditionals within each section body.
    # This must happen BEFORE @-ref resolution so that conditional
    # selection (e.g., choosing between @:Oratio_ and @:Oratio_:s/.../)
    # is done first.
    sections = [_process_section_conditionals(s, config) for s in sections]

    # Phase 4: Resolve section-level @ includes (iterative),
    # including self-references (@:SectionName).
    all_sections_map = {s.header.name: s for s in sections}
    sections = [
        _resolve_section_refs(s, config, base, all_sections_map) for s in sections
    ]

    # Phase 5: Filter display markers based on Mass type.
    preamble = _filter_display_markers(preamble, config)
    sections = [
        Section(header=s.header, body=_filter_display_markers(s.body, config))
        for s in sections
    ]

    # Phase 6: Expand $ macros (prayer conclusions).
    prayers_db = _get_prayers_db(base, config.language)
    preamble = _expand_macros(preamble, prayers_db)
    sections = [
        Section(header=s.header, body=_expand_macros(s.body, prayers_db))
        for s in sections
    ]

    # Phase 7: Expand static & subroutines (&Gloria, &DominusVobiscum, entities).
    preamble = _expand_subroutines(preamble, prayers_db)
    sections = [
        Section(header=s.header, body=_expand_subroutines(s.body, prayers_db))
        for s in sections
    ]

    # Phase 8: Remove empty sections.
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
    seen_names: dict[str, int] = {}

    for section in sections:
        name = section.header.name

        if section.header.rubric is not None:
            condition_met = vero(section.header.rubric.expression, config)

            if name in seen_names:
                if condition_met:
                    result[seen_names[name]] = Section(
                        header=SectionHeader(
                            kind=LineKind.SECTION_HEADER,
                            raw=section.header.raw,
                            line_number=section.header.line_number,
                            name=name,
                            rubric=None,
                        ),
                        body=section.body,
                    )
            else:
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
        else:
            if name not in seen_names:
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
            ref_doc = _load_referenced_file(line.file_ref, None, base)
            if ref_doc:
                for ref_section in ref_doc.sections:
                    if ref_section.header.name not in existing_names:
                        sections.append(ref_section)
                        existing_names.add(ref_section.header.name)
        else:
            new_preamble.append(line)

    return new_preamble, sections


# ---------------------------------------------------------------------------
# Phase 3: Section-level @ resolution (including self-references)
# ---------------------------------------------------------------------------


def _resolve_section_refs(
    section: Section,
    config: MissalConfig,
    base: Path,
    all_sections: dict[str, Section],
) -> Section:
    """Resolve @-references within a section body (iteratively, max 7 deep).

    Self-references (``@:SectionName``) are resolved by looking up the
    named section in ``all_sections`` (the document's own sections).
    """
    body = list(section.body)

    for _iteration in range(_MAX_REF_DEPTH):
        new_body: list[Line] = []
        had_refs = False

        for line in body:
            if isinstance(line, CrossRef):
                had_refs = True
                resolved_lines = _resolve_single_ref(
                    line, section.header.name, config, base, all_sections
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
    all_sections: dict[str, Section],
) -> list[Line]:
    """Resolve a single @-reference to its content lines.

    Returns the replacement lines, or the original ref line if resolution
    fails (so the user can see what couldn't be resolved).
    """
    target_section = ref.section_ref or current_section_name

    # --- Self-reference: @:SectionName ---
    if ref.is_self_ref:
        if not ref.section_ref:
            return [ref]

        target_name = ref.section_ref
        if target_name in all_sections:
            lines = list(all_sections[target_name].body)
            if ref.substitutions:
                lines = _apply_substitutions(lines, ref.substitutions)
            return lines
        return [ref]

    # --- External file reference ---
    if not ref.file_ref:
        return [ref]

    ref_doc = _load_referenced_file(ref.file_ref, target_section, base)
    if ref_doc is None:
        return [ref]

    target = ref_doc.get_section(target_section)
    if target is None:
        if ref.section_ref is None and ref_doc.preamble:
            lines = list(ref_doc.preamble)
        else:
            return [ref]
    else:
        lines = list(target.body)

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
    ref_path = file_ref.strip()

    if not ref_path.endswith(".txt"):
        ref_path += ".txt"

    full_path = base / ref_path

    if not full_path.is_file():
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

    Backslash-escaped spaces in patterns (``\\ ``) are converted to
    literal spaces before applying the regex.
    """
    remaining = subs.strip()

    for m in re.finditer(
        r"(?:s/(?P<s>[^/]*)/(?P<r>[^/]*)/(?P<f>[gism]*))"
        r"|(?:(?P<n>!?)(?P<b>\d+)(?:-(?P<e>\d+))?)",
        remaining,
    ):
        if m.group("b"):
            start = int(m.group("b")) - 1
            end = int(m.group("e")) if m.group("e") else start + 1
            negate = bool(m.group("n"))

            if negate:
                lines = lines[:start] + lines[end:]
            else:
                lines = lines[start:end]
        elif m.group("s") is not None:
            pattern = m.group("s").replace("\\ ", " ")
            replacement = m.group("r").replace("\\ ", " ")
            flags_str = m.group("f") or ""

            re_flags = 0
            count = 1
            if "g" in flags_str:
                count = 0
            if "i" in flags_str:
                re_flags |= re.IGNORECASE
            if "m" in flags_str:
                re_flags |= re.MULTILINE
            if "s" in flags_str:
                re_flags |= re.DOTALL

            new_lines: list[Line] = []
            for line in lines:
                try:
                    new_raw = re.sub(
                        pattern, replacement, line.raw, count=count, flags=re_flags
                    )
                except re.error:
                    new_lines.append(line)
                    continue
                if new_raw != line.raw:
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

_RE_CONDITIONAL_CONTENT = re.compile(
    r"^\s*"
    r"(?:(?P<stopwords>(?:(?:sed|vero|atque|attamen|si|deinde)\s*)+))?"
    r"(?P<condition>.*?)"
    r"(?:\s+(?P<scope>dicitur|dicuntur|omittitur|omittuntur|semper"
    r"|loco\s+hujus\s+versus|loco\s+horum\s+versuum))?"
    r"\s*$",
    re.IGNORECASE,
)

_BACKSCOPED_STOPWORDS = {"sed", "vero", "atque", "attamen"}

_STOPWORD_WEIGHTS = {
    "si": 0,
    "sed": 1,
    "vero": 1,
    "deinde": 1,
    "atque": 2,
    "attamen": 3,
}


def _process_section_conditionals(section: Section, config: MissalConfig) -> Section:
    """Process inline conditionals within a section body."""
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
                    _backscope_remove(output, parsed["backscope_level"])
                    i += 1
                    continue
                elif has_backscope and not is_omission:
                    _backscope_remove(output, parsed["backscope_level"])
                    i += 1
                    continue
                else:
                    i += 1
                    continue
            else:
                if is_omission:
                    i += 1
                    continue
                elif has_backscope:
                    i += 1
                    scope = parsed["forward_scope"]
                    if scope == "line":
                        if i < len(body) and not isinstance(body[i], ConditionalLine):
                            i += 1
                    continue
                else:
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

    stopwords = re.findall(
        r"\b(sed|vero|atque|attamen|si|deinde)\b", stopwords_str, re.IGNORECASE
    )
    strength = sum(_STOPWORD_WEIGHTS.get(sw.lower(), 0) for sw in stopwords)
    has_backscope = any(sw.lower() in _BACKSCOPED_STOPWORDS for sw in stopwords)

    result["strength"] = strength
    result["has_backscope"] = has_backscope

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
        output.pop()
    elif level == "chunk":
        while output and not isinstance(output[-1], ConditionalLine):
            output.pop()
            if not output:
                break
    elif level == "nest":
        while output and not isinstance(output[-1], ConditionalLine):
            output.pop()
            if not output:
                break


# ---------------------------------------------------------------------------
# Phase 5: Display marker filtering
# ---------------------------------------------------------------------------


def _filter_display_markers(lines: list[Line], config: MissalConfig) -> list[Line]:
    """Filter lines based on ``!*S``/``!*R``/``!*D``/``!*nD`` display markers."""
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
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if (
                        isinstance(next_line, ScriptureRef)
                        and next_line.is_display_marker
                        and next_line.display_marker
                    ):
                        break
                    if next_line.kind == LineKind.HEADING:
                        break
                    i += 1
                continue
            else:
                i += 1
                continue
        else:
            output.append(line)
            i += 1

    return output


def _should_skip_marker(marker: str, config: MissalConfig) -> bool:
    """Determine if a display marker's content should be skipped."""
    skip = False

    if marker.startswith("&"):
        return False

    if "nD" in marker and config.is_requiem:
        skip = True

    if "D" in marker and "nD" not in marker and not config.is_requiem:
        skip = True

    if "S" in marker and "Sn" not in marker and not config.is_solemn:
        skip = True

    if "R" in marker and config.is_solemn:
        skip = True

    return skip


# ---------------------------------------------------------------------------
# Phase 6: $ macro expansion
# ---------------------------------------------------------------------------


def _expand_macros(lines: list[Line], prayers_db: dict[str, list[Line]]) -> list[Line]:
    """Expand ``$MacroName`` lines by looking up the Prayers.txt database.

    The macro name is matched against section names in Prayers.txt.
    A trailing period is stripped for lookup (``$Per Dominum.`` ->
    ``Per Dominum``).
    """
    output: list[Line] = []

    for line in lines:
        if isinstance(line, MacroRef):
            macro_name = line.macro_name.strip().rstrip(".")

            if macro_name in prayers_db:
                output.extend(prayers_db[macro_name])
            else:
                # Macro not found — keep as-is
                output.append(line)
        else:
            output.append(line)

    return output


# ---------------------------------------------------------------------------
# Phase 7: & subroutine expansion (static cases only)
# ---------------------------------------------------------------------------

# Subroutine names that map to a Prayers.txt section.
_SUBROUTINE_PRAYER_MAP: dict[str, str] = {
    "DominusVobiscum": "Dominus vobiscum",
    "Dominus_vobiscum": "Dominus vobiscum",
    "Benedicamus_Domino": "Benedicamus Domino",
    "pater_noster": "Pater noster",
}


def _expand_subroutines(
    lines: list[Line], prayers_db: dict[str, list[Line]]
) -> list[Line]:
    """Expand static ``&`` subroutine references.

    Handles:
    - ``&Gloria`` / ``&Glória``: replaced by the Gloria Patri from Prayers.txt.
    - ``&DominusVobiscum``, ``&Dominus_vobiscum``, ``&Benedicamus_Domino``,
      ``&pater_noster``: replaced by their Prayers.txt sections.
    - ``&Alpha``, ``&Omega``, ``&Psi``: replaced by Unicode characters.
    - Other ``&`` calls (dynamic Perl functions like ``&introitus``,
      ``&collect``, etc.): kept as-is.
    """
    output: list[Line] = []

    for line in lines:
        if isinstance(line, GloriaRef):
            # &Gloria -> Gloria Patri from Prayers.txt
            if "Gloria" in prayers_db:
                output.extend(prayers_db["Gloria"])
            else:
                output.append(line)
        elif isinstance(line, SubroutineRef):
            name = line.function_name

            # Check HTML entities
            if name in _HTML_ENTITIES:
                output.append(
                    TextLine(
                        kind=LineKind.TEXT,
                        raw=_HTML_ENTITIES[name],
                        line_number=line.line_number,
                        body=_HTML_ENTITIES[name],
                    )
                )
            # Check prayer-mapped subroutines
            elif name in _SUBROUTINE_PRAYER_MAP:
                prayer_name = _SUBROUTINE_PRAYER_MAP[name]
                if prayer_name in prayers_db:
                    output.extend(prayers_db[prayer_name])
                else:
                    output.append(line)
            else:
                # Dynamic subroutine — keep as-is
                output.append(line)
        else:
            output.append(line)

    return output
