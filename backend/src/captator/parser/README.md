# captator.parser

Parser for Divinum Officium `.txt` document files.  Converts the
line-oriented text format used by the
[Divinum Officium](https://github.com/DivinumOfficium/divinum-officium)
project into a typed Abstract Syntax Tree (AST).

## Architecture

The parser uses a two-phase design:

```
  raw text
     |
     v
 +----------------+     +------------------+     +---------------+
 | DOLineLexer    | --> | Lark LALR(1)     | --> | DOTransformer |
 | (line-level    |     | parser           |     | (parse tree   |
 |  classification)|    | (structure)      |     |  -> AST)      |
 +----------------+     +------------------+     +---------------+
                                                        |
                                                        v
                                                   Document AST
```

1. **Custom lexer** (`lexer.py`): Classifies each non-blank line into
   one of 22 token types based on its prefix characters and the current
   section context.  This is a line-level lexer, not a character-level
   one -- each token represents an entire line.

2. **LALR(1) grammar** (`divinum_officium.lark`): A Lark grammar that
   consumes the classified tokens and builds a parse tree.  The grammar
   captures the document structure: an optional preamble followed by
   zero or more sections, each with a header and body lines.

3. **Transformer** (`transformer.py`): Converts the Lark parse tree
   into typed AST dataclass nodes defined in `ast_nodes.py`.

### Why LALR(1)?

The Divinum Officium format is line-oriented with no deep nesting.
Section headers (`[Name]`) are unambiguous delimiters and only one token
of lookahead is needed.  LALR(1) is the most efficient parser type that
handles this, and it is Lark's default.

### Why a custom lexer?

Some line types are **context-dependent**: a line like `Gloria` is a
rule directive inside a `[Rule]` section but plain text inside
`[Communio]`.  The custom lexer tracks the current section name and
classifies accordingly.  This is cleaner than encoding context into the
grammar itself.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Public API: `Tokenizer`, `parse()`, `parse_file()`, re-exports all AST types |
| `ast_nodes.py` | 20+ dataclass AST node types (`Document`, `Section`, `SectionHeader`, `CrossRef`, etc.) |
| `lexer.py` | Custom line-level lexer (`DOLineLexer`) with context-aware classification |
| `transformer.py` | Lark Transformer that builds the AST from the parse tree |
| `divinum_officium.lark` | LALR(1) grammar with 22 declared terminal types |

## AST hierarchy

```
Document
  preamble: list[Line]          # Lines before the first [Section]
  sections: list[Section]
    header: SectionHeader
      name: str                 # e.g., "Introitus", "Rank", "Rule"
      rubric: RubricCondition?  # e.g., (rubrica 1960)
    body: list[Line]            # One of the 22 line types below
```

## Line types (22 token types)

| Token | Prefix | AST Node | Example |
|-------|--------|----------|---------|
| `SECTION_HEADER` | `[Name]` | `SectionHeader` | `[Introitus]` |
| `SECTION_HEADER_WITH_RUBRIC` | `[Name] (cond)` | `SectionHeader` | `[Rank] (rubrica 1960)` |
| `CROSS_REF` | `@` | `CrossRef` | `@Tempora/Nat2-0:Evangelium` |
| `MACRO_REF` | `$` | `MacroRef` | `$Per Dominum` |
| `SUBROUTINE_REF` | `&` | `SubroutineRef` | `&psalm(94)` |
| `GLORIA_REF` | `&Gloria` | `GloriaRef` | `&Gloria` |
| `SCRIPTURE_REF` | `!` | `ScriptureRef` | `!Ps 24:1-3` |
| `HEADING_LINE` | `#` | `Heading` | `# Introitus` |
| `SEPARATOR` | `_` | `Separator` | `_` |
| `VERSICLE` | `v.` | `Versicle` | `v. Ecce, advenit...` |
| `DIALOG_VERSICLE` | `V.` | `DialogVersicle` | `V. Dominus vobiscum.` |
| `DIALOG_RESPONSE` | `R.` | `DialogResponse` | `R. Et cum spiritu tuo.` |
| `SHORT_RESPONSE_BR` | `R.br.` | `ShortResponseBr` | `R.br. In omnem terram...` |
| `RESPONSE_LINE` | `r.` | `Response` | `r. Per Dominum nostrum...` |
| `PRIEST_LINE` | `S.` | `PriestLine` | `S. Introibo ad altare Dei.` |
| `MINISTER_LINE` | `M.` | `MinisterLine` | `M. Ad Deum, qui laetificat...` |
| `CONGREGATION_LINE` | `O.` | `CongregationLine` | `O. Sancta Maria...` |
| `DEACON_LINE` | `D.` | `DeaconLine` | `D. Jube, domne...` |
| `RANK_VALUE` | `;;` fields | `RankValue` | `Name;;Duplex;;5.6;;ex C1` |
| `RULE_DIRECTIVE` | *(in [Rule])* | `RuleDirective` | `Gloria`, `Prefatio=Nat` |
| `CONDITIONAL_LINE` | `(...)` | `ConditionalLine` | `(sed rubrica 1960)` |
| `WAIT_DIRECTIVE` | `waitN` | `WaitDirective` | `wait10` |
| `CHANT_REF_LINE` | `{:...:}` | `ChantRef` | `{:H-VespFeria:}v. Text` |
| `TEXT_LINE` | *(default)* | `TextLine` | `Deus, judicium tuum Regi da.` |

## Usage

### Parse a file into an AST

```python
from captator.parser import parse_file

doc = parse_file("path/to/missa/Latin/Sancti/01-06.txt")

print(doc.get_section_names())
# ['Rank', 'Rule', 'Introitus', 'Oratio', 'Lectio', ...]

rank = doc.get_section("Rank")
for line in rank.body:
    print(line.kind, line.raw)
```

### Parse a string

```python
from captator.parser import parse

doc = parse("""
[Introitus]
!Malach 3:1
v. Ecce, advenit dominator Dominus.
&Gloria
v. Ecce, advenit dominator Dominus.
""")

for line in doc.sections[0].body:
    print(f"{line.kind.name}: {line.raw.strip()}")
# SCRIPTURE_REF: !Malach 3:1
# VERSICLE: v. Ecce, advenit dominator Dominus.
# GLORIA_REF: &Gloria
# VERSICLE: v. Ecce, advenit dominator Dominus.
```

### Tokenize only (no AST)

Useful for LSP development -- gives line numbers and token types:

```python
from captator.parser import Tokenizer

tokens = Tokenizer(open("path/to/file.txt").read())
print(f"{len(tokens)} tokens")

for t in tokens:
    print(f"line {t.line}: {t.type}")

# Filter by type
cross_refs = [t for t in tokens if t.type == "CROSS_REF"]
```

### Access AST node fields

Each line type is a dataclass with typed fields:

```python
from captator.parser import parse_file, CrossRef, RankValue, MacroRef

doc = parse_file("path/to/Sancti/01-01.txt")

for section in doc.sections:
    for line in section.body:
        if isinstance(line, CrossRef):
            print(f"Ref: file={line.file_ref} section={line.section_ref}")
        elif isinstance(line, RankValue):
            print(f"Rank: {line.display_name} -- {line.rank_class} ({line.weight})")
        elif isinstance(line, MacroRef):
            print(f"Macro: ${line.macro_name}")
```

### Find sections with rubric conditions

```python
doc = parse_file("path/to/Sancti/12-28.txt")

# Get all [Rank] variants (including conditional ones)
ranks = doc.get_sections("Rank")
for s in ranks:
    cond = s.header.rubric.expression if s.header.rubric else "default"
    print(f"[Rank] ({cond}): {len(s.body)} lines")
```

## Coverage

The parser successfully parses all 1062 Latin Missa `.txt` files from
the Divinum Officium data with zero failures.
