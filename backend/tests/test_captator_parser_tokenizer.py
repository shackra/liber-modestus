"""Tests for the Divinum Officium document tokenizer.

The Tokenizer classifies each non-blank line of a DO .txt file into a
typed token. These tests verify correct line-level classification.
"""

from sacrum.captator import parser

# ---------------------------------------------------------------------------
# Basic tokenization: verify line counts and token types
# ---------------------------------------------------------------------------


def test_tokenize_rank_section():
    """A [Rank] section with a rank value line produces 2 tokens."""
    text = """
    [Rank]
Secunda die infra Octavam Epiphaniæ;;Semiduplex;;5.6;;ex Sancti/01-06
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 2
    assert tokenized.types() == ["SECTION_HEADER", "RANK_VALUE"]


def test_tokenize_rule_section():
    """A [Rule] section classifies its body lines as RULE_DIRECTIVE."""
    text = """
    [Rule]
Gloria
CredoDA
Prefatio=Epi
Suffragium=Maria2;Papa;Ecclesia;;
Infra octavam Epiphaniæ Domini
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 6
    assert tokenized[0].type == "SECTION_HEADER"
    # All body lines in [Rule] are rule directives
    for t in tokenized[1:]:
        assert (
            t.type == "RULE_DIRECTIVE"
        ), f"Expected RULE_DIRECTIVE, got {t.type} for {t!r}"


def test_tokenize_introitus_section():
    """An [Introitus] section with scripture refs, versicles, and &Gloria."""
    text = """
    [Introitus]
!Malach 3:1; 1 Par 29:12
v. Ecce, advénit dominátor Dóminus: et regnum in manu ejus et potéstas et impérium.
!Ps 71:1
Deus, judícium tuum Regi da: et justítiam tuam Fílio Regis.
&Gloria
v. Ecce, advénit dominátor Dóminus: et regnum in manu ejus et potéstas et impérium.
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 7
    types = tokenized.types()
    assert types == [
        "SECTION_HEADER",
        "SCRIPTURE_REF",
        "VERSICLE",
        "SCRIPTURE_REF",
        "TEXT_LINE",
        "GLORIA_REF",
        "VERSICLE",
    ]


def test_tokenize_multiple_sections_with_cross_refs():
    """Multiple sections with cross-references and conditional headers."""
    text = """
    [Evangelium]
@Tempora/Nat2-0

[Offertorium]
@Tempora/Nat30

[Secreta]
@Commune/C2

[Commemoratio Secreta] (rubrica tridentina)
!Pro S. Stephano Protomartyre
@Sancti/08-03:Secreta
!Pro S. Joanne Evangelista
@Sancti/12-27:Secreta
!Pro Ss. Innocentibus
@Sancti/12-28:Secreta

[Communio]
@Tempora/Nat30
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 15
    # Section headers
    assert tokenized[0].type == "SECTION_HEADER"  # [Evangelium]
    assert tokenized[2].type == "SECTION_HEADER"  # [Offertorium]
    assert tokenized[4].type == "SECTION_HEADER"  # [Secreta]
    assert (
        tokenized[6].type == "SECTION_HEADER_WITH_RUBRIC"
    )  # [Commemoratio Secreta] (rubrica tridentina)
    assert tokenized[13].type == "SECTION_HEADER"  # [Communio]
    # Cross-refs
    assert tokenized[1].type == "CROSS_REF"
    assert tokenized[3].type == "CROSS_REF"
    assert tokenized[5].type == "CROSS_REF"


# ---------------------------------------------------------------------------
# Line type classification
# ---------------------------------------------------------------------------


def test_classify_section_header():
    tokenized = parser.Tokenizer("[Rank]\n")
    assert len(tokenized) == 1
    assert tokenized[0].type == "SECTION_HEADER"


def test_classify_section_header_with_rubric():
    tokenized = parser.Tokenizer("[Commemoratio Oratio] (rubrica tridentina)\n")
    assert len(tokenized) == 1
    assert tokenized[0].type == "SECTION_HEADER_WITH_RUBRIC"


def test_classify_cross_ref():
    tokenized = parser.Tokenizer("[X]\n@Tempora/Nat2-0:Evangelium\n")
    assert tokenized[1].type == "CROSS_REF"


def test_classify_self_cross_ref():
    tokenized = parser.Tokenizer("[X]\n@:Ant Vespera\n")
    assert tokenized[1].type == "CROSS_REF"


def test_classify_macro_ref():
    tokenized = parser.Tokenizer("[X]\n$Per Dominum\n")
    assert tokenized[1].type == "MACRO_REF"


def test_classify_subroutine_ref():
    tokenized = parser.Tokenizer("[X]\n&introitus\n")
    assert tokenized[1].type == "SUBROUTINE_REF"


def test_classify_subroutine_with_args():
    tokenized = parser.Tokenizer("[X]\n&psalm(94)\n")
    assert tokenized[1].type == "SUBROUTINE_REF"


def test_classify_gloria_ref():
    tokenized = parser.Tokenizer("[X]\n&Gloria\n")
    assert tokenized[1].type == "GLORIA_REF"


def test_classify_scripture_ref():
    tokenized = parser.Tokenizer("[X]\n!Ps 24:1-3\n")
    assert tokenized[1].type == "SCRIPTURE_REF"


def test_classify_display_marker():
    tokenized = parser.Tokenizer("[X]\n!*S\n")
    assert tokenized[1].type == "SCRIPTURE_REF"


def test_classify_heading():
    tokenized = parser.Tokenizer("# Introitus\n")
    assert tokenized[0].type == "HEADING_LINE"


def test_classify_separator():
    tokenized = parser.Tokenizer("[X]\n_\n")
    assert tokenized[1].type == "SEPARATOR"


def test_classify_versicle():
    tokenized = parser.Tokenizer("[X]\nv. Ecce, advénit dominátor Dóminus\n")
    assert tokenized[1].type == "VERSICLE"


def test_classify_dialog_versicle():
    tokenized = parser.Tokenizer("[X]\nV. Dóminus vobíscum.\n")
    assert tokenized[1].type == "DIALOG_VERSICLE"


def test_classify_dialog_response():
    tokenized = parser.Tokenizer("[X]\nR. Et cum spíritu tuo.\n")
    assert tokenized[1].type == "DIALOG_RESPONSE"


def test_classify_short_response_br():
    tokenized = parser.Tokenizer("[X]\nR.br. In omnem terram * Exívit sonus eórum.\n")
    assert tokenized[1].type == "SHORT_RESPONSE_BR"


def test_classify_response():
    tokenized = parser.Tokenizer("[X]\nr. Per Dóminum nostrum.\n")
    assert tokenized[1].type == "RESPONSE_LINE"


def test_classify_priest():
    tokenized = parser.Tokenizer("[X]\nS. Introíbo ad altáre Dei.\n")
    assert tokenized[1].type == "PRIEST_LINE"


def test_classify_minister():
    tokenized = parser.Tokenizer("[X]\nM. Ad Deum, qui lætíficat juventútem meam.\n")
    assert tokenized[1].type == "MINISTER_LINE"


def test_classify_congregation():
    tokenized = parser.Tokenizer("[X]\nO. Sancta María, Mater Dei.\n")
    assert tokenized[1].type == "CONGREGATION_LINE"


def test_classify_deacon():
    tokenized = parser.Tokenizer("[X]\nD. Jube, domne, benedícere.\n")
    assert tokenized[1].type == "DEACON_LINE"


def test_classify_rank_value():
    tokenized = parser.Tokenizer("[Rank]\nIn Epiphania Domini;;Duplex I classis;;7\n")
    assert tokenized[1].type == "RANK_VALUE"


def test_classify_rank_value_with_empty_name():
    tokenized = parser.Tokenizer("[Rank]\n;;Duplex I classis;;6.1;;\n")
    assert tokenized[1].type == "RANK_VALUE"


def test_classify_conditional():
    tokenized = parser.Tokenizer("[Rank]\n(sed rubrica 1960)\n")
    assert tokenized[1].type == "CONDITIONAL_LINE"


def test_classify_wait_directive():
    tokenized = parser.Tokenizer("[X]\nwait10\n")
    assert tokenized[1].type == "WAIT_DIRECTIVE"


def test_classify_chant_ref():
    tokenized = parser.Tokenizer("[X]\n{:H-VespFeria:}v. Lucis Creátor óptime,\n")
    assert tokenized[1].type == "CHANT_REF_LINE"


def test_classify_text():
    tokenized = parser.Tokenizer("[X]\nDeus, judícium tuum Regi da.\n")
    assert tokenized[1].type == "TEXT_LINE"


# ---------------------------------------------------------------------------
# Context-dependent classification
# ---------------------------------------------------------------------------


def test_rule_section_classifies_body_as_directives():
    """Inside a [Rule] section, lines are classified as RULE_DIRECTIVE."""
    text = "[Rule]\nGloria\nCredo\nPrefatio=Epi\n"
    tokenized = parser.Tokenizer(text)
    assert tokenized[1].type == "RULE_DIRECTIVE"
    assert tokenized[2].type == "RULE_DIRECTIVE"
    assert tokenized[3].type == "RULE_DIRECTIVE"


def test_outside_rule_section_gloria_is_text():
    """Outside a [Rule] section, 'Gloria' is plain text (not a directive)."""
    text = "[Introitus]\nGloria in excelsis Deo.\n"
    tokenized = parser.Tokenizer(text)
    assert tokenized[1].type == "TEXT_LINE"


def test_rank_value_not_matched_in_rule_section():
    """Double-semicolons in [Rule] body are rule directives, not rank values."""
    text = "[Rule]\nSuffragium=Maria2;Papa;Ecclesia;;\n"
    tokenized = parser.Tokenizer(text)
    assert tokenized[1].type == "RULE_DIRECTIVE"
