# Liber Modestus -- Backend

Backend for **Liber Modestus**: a traditional Roman Catholic Missal that
parses, resolves, and presents Mass propers from the
[Divinum Officium](https://github.com/DivinumOfficium/divinum-officium)
data files.

Given a calendar date and a missal configuration (rubrical edition, Mass
type, language), the backend determines which Mass propers to use and
returns a fully resolved document ready for presentation.

## Architecture

The backend is organised into three modules that form a pipeline:

```
  date + config
       |
       v
 +--------------+     +------------+     +-----------+
 | directorium  | --> |   parser   | --> |  resolver  |
 | (calendar)   |     | (AST)      |     | (resolve)  |
 +--------------+     +------------+     +-----------+
       |                                       |
       v                                       v
  MassDay                              Document (resolved)
  (winner, commemorations)             (ready for display)
```

| Module | Purpose | README |
|--------|---------|--------|
| [`captator.parser`](src/captator/parser/README.md) | Parse `.txt` files into a typed AST | Line-level lexer, LALR(1) grammar, 22 node types |
| [`captator.resolver`](src/captator/resolver/README.md) | Evaluate conditions, resolve cross-references, expand macros | 8-phase pipeline, rubric conditions, language layering |
| [`captator.directorium`](src/captator/directorium/README.md) | Liturgical calendar engine | Temporal cycle, sanctoral Kalendar, occurrence, transfers |
| `captator.options` | Frontend-facing option sets | Rubrics, Mass types, languages, votives, communes, Ordo variants |
| `captator.assembly` | Combine Ordo (canon) + Propers into complete Mass | Template substitution, preface/communicantes selection |

## Prerequisites

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) (package manager)
- The `divinum-officium` submodule (liturgical data files)

## Setup

```bash
cd backend

# Initialise the submodule (if not already done)
git submodule update --init --recursive

# Install dependencies
uv sync
```

## Running tests

```bash
uv run pytest -v
```

The test suite includes unit tests for each module and integration tests
that parse and resolve all 1062 Latin Missa files from the Divinum
Officium data.

## Quick start

### Get the Mass propers for a given date

```python
from datetime import date
from captator.directorium import get_mass_day
from captator.resolver import MissalConfig, Rubric, MassType

config = MissalConfig(
    rubric=Rubric.RUBRICAE_1960,   # 1962 Missal
    mass_type=MassType.READ,       # Low Mass
    language="English",            # Prayer conclusions in English
)

day = get_mass_day(
    date(2025, 12, 25),
    config,
    tabulae_path="src/divinum-officium/web/www/Tabulae",
    missa_path="src/divinum-officium/web/www/missa/Latin",
)

# What Mass is celebrated today?
print(day.occurrence.winner_file)       # 'Sancti/12-25'
print(day.occurrence.winner_name)       # 'In Nativitate Domini'
print(day.occurrence.commemorations)    # []
print(day.occurrence.is_requiem)        # False

# The fully resolved document (conditions evaluated, @refs inlined,
# macros expanded, display markers filtered):
doc = day.resolved_document
for section in doc.sections:
    print(f"[{section.header.name}]")
    for line in section.body:
        print(f"  {line.raw}")
```

### Assemble a complete Mass (Ordo + Propers)

```python
from datetime import date
from captator.directorium import get_mass_day
from captator.assembly import assemble_mass
from captator.resolver import MissalConfig, Rubric, MassType

config = MissalConfig(rubric=Rubric.RUBRICAE_1960, mass_type=MassType.READ)
day = get_mass_day(
    date(2025, 1, 6), config,
    tabulae_path="path/to/Tabulae",
    missa_path="path/to/missa/Latin",
)

# Assemble: Ordo template + day's propers + correct preface + communicantes
complete = assemble_mass(
    propers=day.resolved_document,
    config=config,
    missa_path="path/to/missa/Latin",
    ordo="Ordo",  # or "OrdoOP" (Dominican), "OrdoS" (Sarum), etc.
)

# The result is a Document with the entire Mass from Prayers at the
# Foot of the Altar through the Last Gospel:
for line in complete.preamble:
    print(line.raw)
```

The assembly layer handles:
- Inserting the day's Introitus, Collect, Epistle, Gradual, Gospel,
  Offertory, Secret, Communion antiphon, and Postcommunion at the
  correct positions in the Ordo template.
- Selecting the proper **Preface** from `Prefationes.txt` based on the
  `Prefatio=` rule in the propers or the liturgical season.
- Selecting the correct **Communicantes** variant in the Canon (with
  St. Joseph for 1962, seasonal variants for Christmas/Easter/etc.).
- Inserting the special **Hanc igitur** during Easter and Pentecost
  octaves.
- Supporting 6 different Ordo (canon/rite) variants: Roman, Dominican,
  Sarum, Ambrosian, Mozarabic, and 1965-1967 transitional.

### Parse a single file without calendar logic

```python
from captator.parser import parse_file

doc = parse_file("path/to/missa/Latin/Sancti/01-06.txt")
print(doc.get_section_names())
# ['Rank', 'Rule', 'Introitus', 'Oratio', 'Lectio', ...]
```

### Resolve a parsed document

```python
from captator.parser import parse_file
from captator.resolver import MissalConfig, Rubric, resolve

doc = parse_file("path/to/missa/Latin/Sancti/01-06.txt")
config = MissalConfig(rubric=Rubric.RUBRICAE_1960, language="Latin")
resolved = resolve(doc, config, base_path="path/to/missa/Latin")

# Resolved: conditions evaluated, @refs inlined, $macros expanded
for section in resolved.sections:
    print(f"[{section.header.name}] -- {len(section.body)} lines")
```

### Inspect tokens (useful for LSP development)

```python
from captator.parser import Tokenizer

tokens = Tokenizer(open("path/to/file.txt").read())
for t in tokens:
    print(f"line {t.line}: {t.type} = {t.value[:60]}")
```

### Get available options for the frontend

```python
from captator.options import get_mass_options

opts = get_mass_options()

# Each field is a tuple of Option(value, label, description)
for o in opts.rubrics:
    print(f"{o.value}: {o.label}")
# RUBRICAE_1960: Rubrics 1960 (1962 Missal)
# RUBRICAE_1955: Reduced 1955
# TRIDENT_1930: Divino Afflatu (~1930)
# ...

for o in opts.votives:
    print(f"{o.value}: {o.label}")
# Hodie: Hodie (Mass of the day)
# C2: Unius Martyris Pontificis: Statuit
# ...
# C9: Defunctorum quotidianis: Requiem aeternam
# ...

# Available fields: rubrics, mass_types, orders, languages, votives, communes, ordines
# ordines = Ordo/canon variants (Roman, Dominican, Sarum, etc.)
```

To check which languages are actually present on disk:

```python
from captator.options import get_languages_from_disk

langs = get_languages_from_disk("path/to/missa")
for o in langs:
    print(o.value)  # "Latin", "English", "Espanol", ...
```

## Supported rubrical editions

| Enum value | Edition | Year |
|------------|---------|------|
| `Rubric.TRIDENT_1570` | Original Tridentine (Pius V) | 1570 |
| `Rubric.TRIDENT_1910` | Divino Afflatu (Pius X) | 1911 |
| `Rubric.TRIDENT_1930` | Post-Divino Afflatu (Pius XI) | ~1930 |
| `Rubric.RUBRICAE_1955` | Simplified rubrics (Pius XII) | 1955 |
| `Rubric.RUBRICAE_1960` | Code of Rubrics / 1962 Missal (John XXIII) | 1960 |

Each edition affects the liturgical calendar (which feasts exist, their
ranks, octaves, vigils), the temporal file variants used, and the
evaluation of `(rubrica ...)` conditions within the documents.

## Current limitations

- **Commune @refs** that point to `horas/` instead of `missa/` are not
  yet resolved (requires a cross-directory path resolver).
- **Dynamic `&` subroutines** (`&introitus`, `&collect`, etc. in
  `Ordo.txt`) are kept as AST nodes -- they represent runtime Perl
  functions that compose the full Ordo from propers.
- **Concurrence** (Vespers conflict resolution) is not implemented; it
  is only needed for the Divine Office, not for Mass.
- **Temporal rank estimation** uses a heuristic based on the Tempora ID
  rather than parsing the actual `[Rank]` section of the file.  This is
  correct for the vast majority of cases but may produce wrong results
  for unusual ferias (Ember Days, specific vigils).
- **Votive Masses** and **daily Requiem Masses** are user-selected
  options.  The available choices are listed by ``get_mass_options()``
  but the Directorium does not yet apply them when resolving a day.
