# captator.resolver

Document resolver for Divinum Officium Missa files.  Takes a parsed
`Document` AST and a `MissalConfig`, then evaluates rubric conditions,
resolves cross-references, expands macros, and filters display markers
to produce a clean document ready for presentation.

## Pipeline

Resolution proceeds in 8 phases, applied in order:

| Phase | What it does | Example |
|-------|-------------|---------|
| 1. Section variants | Evaluates `[Section] (rubrica ...)` conditions; keeps only the matching variant per section name | `[Rank] (rubrica 1960)` included only with 1960 config |
| 2. Preamble includes | Resolves preamble-level `@File` references as section defaults | `@Commune/C1` fills missing sections |
| 3. Inline conditionals | Processes `(sed rubrica ...)` with backward/forward scoping | Selects correct Rank from 3 variants with `(sed ...)` |
| 4. Section @refs | Resolves `@File:Section:Subs` by loading referenced files and inlining content (max 7 levels deep); includes self-references (`@:Section`) | `@Tempora/Nat30` replaced with actual Introitus text |
| 5. Display markers | Filters `!*S` / `!*R` / `!*D` / `!*nD` lines based on Mass type | Solemn-only rubrics hidden in Low Mass |
| 6. Macro expansion | Expands `$Per Dominum`, `$Qui tecum`, etc. from `Ordo/Prayers.txt` | `$Per Dominum` becomes the full prayer conclusion |
| 7. Subroutine expansion | Expands static `&Gloria`, `&DominusVobiscum`, HTML entities (`&Alpha`, `&Omega`) | `&Gloria` becomes "Gloria Patri, et Filio..." |
| 8. Cleanup | Removes sections that ended up empty after filtering | Conditional sections with no surviving lines |

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Public API: `resolve()`, re-exports config types |
| `config.py` | `MissalConfig`, `Rubric`, `MassType`, `OrderVariant` |
| `evaluator.py` | `vero()` -- rubric condition evaluator (Latin boolean expressions) |
| `resolve.py` | The 8-phase resolution pipeline |

## MissalConfig reference

```python
@dataclass(frozen=True)
class MissalConfig:
    rubric: Rubric              # Rubrical edition (default: RUBRICAE_1960)
    mass_type: MassType         # SOLEMN, READ, or REQUIEM (default: READ)
    order: OrderVariant         # ROMAN, MONASTIC, DOMINICAN, CISTERCIAN
    language: str               # "Latin", "English", "Espanol", etc.
    day_of_week: int            # 1=Sunday, 7=Saturday
    tempus_id: str              # Liturgical period for (tempore ...) conditions
    dayname: str                # Day name code for (die ...) conditions
    commune: str                # Current commune file for (commune ...) conditions
    votive: str                 # Votive Mass identifier
```

### Rubric enum

| Value | Edition |
|-------|---------|
| `Rubric.TRIDENT_1570` | Original Tridentine (Pius V) |
| `Rubric.TRIDENT_1910` | Divino Afflatu (Pius X, 1911) |
| `Rubric.TRIDENT_1930` | Post-Divino Afflatu (Pius XI additions) |
| `Rubric.RUBRICAE_1955` | Simplified rubrics (Pius XII, 1955) |
| `Rubric.RUBRICAE_1960` | Code of Rubrics / 1962 Missal (John XXIII) |

### MassType enum

| Value | Meaning | Effect |
|-------|---------|--------|
| `MassType.SOLEMN` | Missa Solemnis / Cantata | `!*S` sections shown, `!*R` hidden |
| `MassType.READ` | Missa Lecta (Low Mass) | `!*S` hidden, `!*R` shown |
| `MassType.REQUIEM` | Missa Defunctorum | `!*D` shown, `!*nD` hidden |

### OrderVariant enum

| Value | Variant | Directory suffix |
|-------|---------|-----------------|
| `OrderVariant.ROMAN` | Standard Roman Rite | *(none)* |
| `OrderVariant.MONASTIC` | Benedictine | `M` |
| `OrderVariant.DOMINICAN` | Order of Preachers | `OP` |
| `OrderVariant.CISTERCIAN` | Cistercian | `Cist` |

## Rubric condition syntax

The `vero()` function evaluates Latin boolean expressions found in
`(rubrica ...)` conditions.  The grammar:

```
expression := disjunct ('aut' disjunct)*      -- OR (outer)
disjunct   := atom (('et' | 'nisi') atom)*    -- AND / UNLESS (inner)
atom       := [subject] predicate
```

### Subjects

| Subject keyword | Tests against |
|----------------|---------------|
| `rubrica` / `rubricis` | The version string (e.g., "Rubrics 1960") |
| `tempore` | The liturgical period (e.g., "Adventus") |
| `die` | The day name code (e.g., "Adv1-0") |
| `feria` | The day of the week (1-7) |
| `commune` | The current commune file |
| `votiva` | The votive Mass identifier |

### Operators

- `aut` = OR (true if either branch is true)
- `et` = AND (both must be true)
- `nisi` = UNLESS (first atom true, subsequent atoms must be false)

### Examples

| Condition | Meaning |
|-----------|---------|
| `rubrica 1960` | True for 1960 rubrics (regex match: "1960" in version string) |
| `rubrica tridentina` | True for any Tridentine edition ("Trident" in version) |
| `rubrica 196 aut rubrica 1955` | True for 1960 OR 1955 |
| `rubrica tridentina nisi rubrica cisterciensis` | Tridentine but NOT Cistercian |
| `tempore paschali` | During Paschaltide |

## Language layering

Macro expansion (`$Per Dominum`, `&Gloria`, etc.) supports multilingual
output.  The `language` field in `MissalConfig` selects which
`Ordo/Prayers.txt` to load:

1. Latin `Ordo/Prayers.txt` is always loaded as the base layer.
2. If `language` is not `"Latin"`, the translated `Prayers.txt` is
   loaded and its sections override the Latin ones.
3. Sections not present in the translation fall back to Latin
   automatically.

Available languages: Latin, English, Espanol, Francais, Deutsch, Polski,
Italiano, Portugues, Bohemice, Magyar, Nederlands, Ukrainian,
Vietnamice, Dansk.

## Usage

### Basic resolution

```python
from captator.parser import parse_file
from captator.resolver import MissalConfig, Rubric, MassType, resolve

doc = parse_file("path/to/missa/Latin/Sancti/01-06.txt")
config = MissalConfig(
    rubric=Rubric.RUBRICAE_1960,
    mass_type=MassType.READ,
    language="English",
)
resolved = resolve(doc, config, base_path="path/to/missa/Latin")

for section in resolved.sections:
    print(f"[{section.header.name}]")
    for line in section.body:
        print(f"  {line.raw}")
```

### Evaluate a condition directly

```python
from captator.resolver import MissalConfig, Rubric, vero

config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
print(vero("rubrica 1960", config))            # True
print(vero("rubrica tridentina", config))      # False
print(vero("rubrica 196 aut rubrica 1955", config))  # True
```

### Compare editions

```python
from captator.parser import parse_file
from captator.resolver import MissalConfig, Rubric, resolve

doc = parse_file("path/to/missa/Latin/Sancti/01-01.txt")
base = "path/to/missa/Latin"

resolved_1960 = resolve(doc, MissalConfig(rubric=Rubric.RUBRICAE_1960), base)
resolved_trid = resolve(doc, MissalConfig(rubric=Rubric.TRIDENT_1570), base)

# 1960: no Commemoratio sections (suppressed by rubric)
names_1960 = [s.header.name for s in resolved_1960.sections]
assert not any("Commemoratio" in n for n in names_1960)

# Tridentine: Commemoratio sections present
names_trid = [s.header.name for s in resolved_trid.sections]
assert any("Commemoratio" in n for n in names_trid)
```
