# Liber Modestus -- Backend

Backend for **Liber Modestus**: a traditional Roman Catholic Missal that
parses, resolves, and presents Mass propers from the
[Divinum Officium](https://github.com/DivinumOfficium/divinum-officium)
data files.

Given a calendar date and a missal configuration (rubrical edition, Mass
type, language), the backend determines which Mass propers to use and
returns a fully resolved document ready for presentation.

## Architecture

The core pipeline transforms a date and configuration into a complete,
resolved Mass text:

```
  date + MissalConfig
       |
       v
  +--------------+     +------------+     +------------+     +----------+
  | directorium  | --> |   parser   | --> |  resolver  | --> | assembly |
  | (calendar)   |     | (AST)      |     | (resolve)  |     | (ordo)   |
  +--------------+     +------------+     +------------+     +----------+
       |                                       |                   |
       v                                       v                   v
  MassDay / MassInfo                    Document (resolved)   Document
  (winner, color, rank,                 (propers ready        (complete Mass:
   commemorations)                       for display)          Ordo + Propers)
```

Two additional packages provide independent functionality:

```
  date + lat/lng + timezone               "!Ps 24:1-3"
       |                                       |
       v                                       v
  +----------+                           +------------+
  |  horae   |                           | scriptura  |
  | (hours)  |                           | (citations)|
  +----------+                           +------------+
       |                                       |
       v                                       v
  HoraeResult                            NormalizedReference
  (8 canonical hours                     (book, chapter,
   with start/end times)                  verse range)
```

### Modules

| Module                                                                     | Purpose                                                      | Details                                                                                       |
|----------------------------------------------------------------------------|--------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| [`sacrum.captator.directorium`](src/sacrum/captator/directorium/README.md) | Liturgical calendar engine                                   | Temporal cycle, sanctoral Kalendar, occurrence resolution, feast transfers, liturgical colour |
| [`sacrum.captator.parser`](src/sacrum/captator/parser/README.md)           | Parse `.txt` files into a typed AST                          | Line-level lexer, LALR(1) grammar, 22 node types                                              |
| [`sacrum.captator.resolver`](src/sacrum/captator/resolver/README.md)       | Evaluate conditions, resolve cross-references, expand macros | 8-phase pipeline, rubric conditions, language layering                                        |
| `sacrum.captator.assembly`                                                 | Combine Ordo (canon) + Propers into complete Mass            | Template substitution, preface/communicantes selection                                        |
| `sacrum.captator.options`                                                  | Frontend-facing option sets                                  | Rubrics, Mass types, languages, votives, communes, Ordo variants                              |
| `sacrum.tempus`                                                            | Temporal cycle date calculations                             | Easter-relative dates, season boundaries, Tempora IDs                                         |
| `horae`                                                                    | Canonical hours calculator                                   | Temporal (unequal) hours from sunrise/sunset at a geographic location                         |
| `scriptura`                                                                | Scripture reference parser                                   | Bible citation parsing, 73-book canon, verse IDs, 17 locales                                  |

### Data flow

The modules compose in a layered fashion.  Each layer can be used
independently:

1. **Calendar only** -- `directorium.get_mass_info_for_date()` returns
   the feast name, rank, colour, and commemorations for a date.  No
   document parsing is involved.  This is the fastest path and the
   recommended entry point for calendar/iCal generation.

2. **Resolved propers** -- `directorium.get_mass_day()` additionally
   parses and resolves the winning file, returning the full `Document`
   AST with conditions evaluated, `@`-references inlined, `$`-macros
   expanded, and display markers filtered.

3. **Complete Mass** -- `assembly.assemble_mass()` takes the resolved
   propers and inserts them into the Ordo template, selecting the
   correct Preface, Communicantes, and Hanc igitur.

4. **Standalone parsing** -- `parser.parse_file()` and
   `resolver.resolve()` can be used directly on any `.txt` file,
   without the calendar engine.

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

### Calendar generation (iCal, liturgical calendars)

The recommended entry point for building calendars.  Returns the feast
name, liturgical colour, rank class, and commemorations for any date --
without parsing the full document.

```python
from datetime import date
from sacrum.captator.directorium import (
    get_mass_info_for_date,
    get_mass_info_for_year,
    LiturgicalColor,
)
from sacrum.captator.resolver import Rubric

# Single date -- 1962 Missal (default), Spanish translation
info = get_mass_info_for_date(date(2025, 12, 25), language="Espanol")

info.date               # datetime.date(2025, 12, 25)
info.name               # 'In Nativitate Domini' (translated if available)
info.name_canonical     # 'In Nativitate Domini' (always Latin)
info.rank               # 3.0
info.rank_name          # 'Duplex I Classis'
info.color              # LiturgicalColor.WHITE
info.color.value        # 'white'
info.is_sanctoral       # True
info.commemorations     # []

# Gaudete Sunday -- rose vestments
info = get_mass_info_for_date(date(2025, 12, 14))
info.color              # LiturgicalColor.ROSE

# Good Friday -- black vestments
info = get_mass_info_for_date(date(2025, 4, 18))
info.color              # LiturgicalColor.BLACK

# St Joseph -- commemorations from the Lent feria
info = get_mass_info_for_date(date(2025, 3, 19))
info.name_canonical     # 'S. Joseph Sponsi B.M.V. Confessoris'
info.is_sanctoral       # True
info.commemorations     # ['Feria Quarta infra Hebdomadam III...']

# Different rubrical edition
info = get_mass_info_for_date(
    date(2025, 6, 29), rubric=Rubric.TRIDENT_1570
)
info.rank_name          # 'Duplex I classis cum octava communi'
# (vs. 'Duplex I classis' in 1960, where octaves are suppressed)
```

#### Generating an iCal calendar

```python
from datetime import date, datetime
from icalendar import Calendar, Event
from sacrum.captator.directorium import get_mass_info_for_year, LiturgicalColor
import zoneinfo

# Colour names for the CATEGORIES field
_COLOR_LABEL = {
    LiturgicalColor.WHITE: "White",
    LiturgicalColor.RED: "Red",
    LiturgicalColor.GREEN: "Green",
    LiturgicalColor.VIOLET: "Violet",
    LiturgicalColor.BLACK: "Black",
    LiturgicalColor.ROSE: "Rose",
}

cal = Calendar()
cal.add("prodid", "-//Liber Modestus//EN")
cal.add("version", "2.0")
tz = zoneinfo.ZoneInfo("America/Costa_Rica")

for info in get_mass_info_for_year(2025, language="Espanol"):
    event = Event()
    event.add("summary", info.name)
    event.add("dtstart", info.date)
    event.add("description", (
        f"Canonical: {info.name_canonical}\n"
        f"Rank: {info.rank_name}\n"
        f"Colour: {_COLOR_LABEL[info.color]}\n"
        + (f"Commemorations: {', '.join(info.commemorations)}\n"
           if info.commemorations else "")
    ))
    event.add("categories", [_COLOR_LABEL[info.color]])
    cal.add_component(event)

with open("missale_2025.ics", "wb") as f:
    f.write(cal.to_ical())
```

### Mass names (lightweight lookups)

When you only need the feast name (no colour or rank class), use
`get_mass_name_for_date`.  It is slightly faster because it skips the
rank-class extraction and colour computation.

```python
from datetime import date
from sacrum.captator.directorium import (
    get_mass_name_for_date,
    get_mass_names_for_month,
)

m = get_mass_name_for_date(date(2025, 12, 25), language="English")
m.name               # 'Christmas Day' (or translated name if available)
m.name_canonical     # 'In Nativitate Domini'
m.rank               # 3.0
m.is_sanctoral       # True
m.is_commemoration   # False
m.commemorations     # []

# All days of a month
december = get_mass_names_for_month(2025, 12, language="Espanol")
for m in december:
    print(f"{m.name_canonical}: {m.name}")
```

### Get the Mass propers for a given date

```python
from datetime import date
from sacrum.captator.directorium import get_mass_day
from sacrum.captator.resolver import MissalConfig, Rubric, MassType

config = MissalConfig(
    rubric=Rubric.RUBRICAE_1960,   # 1962 Missal
    mass_type=MassType.READ,       # Low Mass
    language="English",            # Prayer conclusions in English
)

day = get_mass_day(
    date(2025, 12, 25),
    config,
    tabulae_path="src/sacrum/divinum-officium/web/www/Tabulae",
    missa_path="src/sacrum/divinum-officium/web/www/missa/Latin",
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
from sacrum.captator.directorium import get_mass_day
from sacrum.captator.assembly import assemble_mass
from sacrum.captator.resolver import MissalConfig, Rubric, MassType

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
from sacrum.captator.parser import parse_file

doc = parse_file("path/to/missa/Latin/Sancti/01-06.txt")
print(doc.get_section_names())
# ['Rank', 'Rule', 'Introitus', 'Oratio', 'Lectio', ...]
```

### Resolve a parsed document

```python
from sacrum.captator.parser import parse_file
from sacrum.captator.resolver import MissalConfig, Rubric, resolve

doc = parse_file("path/to/missa/Latin/Sancti/01-06.txt")
config = MissalConfig(rubric=Rubric.RUBRICAE_1960, language="Latin")
resolved = resolve(doc, config, base_path="path/to/missa/Latin")

# Resolved: conditions evaluated, @refs inlined, $macros expanded
for section in resolved.sections:
    print(f"[{section.header.name}] -- {len(section.body)} lines")
```

### Inspect tokens (useful for LSP development)

```python
from sacrum.captator.parser import Tokenizer

tokens = Tokenizer(open("path/to/file.txt").read())
for t in tokens:
    print(f"line {t.line}: {t.type} = {t.value[:60]}")
```

### Get available options for the frontend

```python
from sacrum.captator.options import get_mass_options

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
from sacrum.captator.options import get_languages_from_disk

langs = get_languages_from_disk("path/to/missa")
for o in langs:
    print(o.value)  # "Latin", "English", "Espanol", ...
```

### Canonical hours

Calculate the eight canonical hours for any date and geographic
location.  Uses temporal (unequal) hours derived from astronomical
sunrise and sunset.

```python
from datetime import date
from horae import get_horae, MatinsMode

result = get_horae(
    date=date(2025, 6, 24),
    latitude=9.9281,         # San Jose, Costa Rica
    longitude=-84.0907,
    timezone="America/Costa_Rica",
    include_prime=True,      # Include the suppressed hour of Prime
    matins_mode=MatinsMode.CATHEDRAL,  # or MONASTIC
)

result.sunrise          # datetime with tzinfo
result.sunset           # datetime with tzinfo
result.day_hour_duration    # timedelta (~1h 10min near summer solstice)
result.night_hour_duration  # timedelta (~0h 50min)

for hora in result.hours:
    print(f"{hora.name:15s}  {hora.start:%H:%M} - {hora.end:%H:%M}"
          f"  ({'day' if hora.is_daytime else 'night'})")
# Matutinum        05:15 - 05:15  (night)
# Laudes           05:15 - 06:25  (day)
# Prima            06:25 - 07:35  (day)
# Tertia           07:35 - 08:46  (day)
# Sexta            08:46 - 09:56  (day)
# Nona             09:56 - 11:06  (day)
# Vesperae         11:06 - 12:16  (day)
# Completorium     17:50 - 18:40  (night)
```

If the location is in a polar region (midnight sun or polar night), the
calculator falls back to a fixed 06:00/18:00 split and sets
`result.fixed_clock_fallback = True`.

### Scripture references

Parse the Vulgate-style citations found in `.txt` files (e.g.,
`!Ps 24:1-3`, `!Matt 2:1-12`) into structured, queryable objects.

```python
from scriptura import parse_citation, book_name, Book

ref = parse_citation("!Ps 24:1-3")
ref.book              # Book.PSALMI
ref.chapter           # 24
ref.verse_start       # 1
ref.verse_end         # 3
ref.verse_ids         # (19024001, 19024002, 19024003)

# Localised book names (17 locales: la, en, es, de, fr, it, ...)
book_name(Book.PSALMI, "la")    # 'Psalmi'
book_name(Book.PSALMI, "es")    # 'Salmos'
book_name(Book.PSALMI, "en")    # 'Psalms'

# Look up a book by abbreviation, full name, or OSIS ID
from scriptura import lookup_book
lookup_book("Gen")       # Book.GENESIS
lookup_book("Psalmi")    # Book.PSALMI
lookup_book("1Cor")      # Book.AD_CORINTHIOS_1
```

## API reference

### Calendar generation

| Function                                                     | Returns          | Description                                                               |
|--------------------------------------------------------------|------------------|---------------------------------------------------------------------------|
| `directorium.get_mass_info_for_date(dt, rubric?, language?)` | `MassInfo`       | Name, canonical name, rank, rank class, colour, commemorations for a date |
| `directorium.get_mass_info_for_month(year, month, ...)`      | `list[MassInfo]` | `MassInfo` for every day of a month                                       |
| `directorium.get_mass_info_for_year(year, ...)`              | `list[MassInfo]` | `MassInfo` for every day of a year                                        |
| `directorium.get_mass_name_for_date(dt, rubric?, language?)` | `MassName`       | Lighter: name + rank + commemorations (no colour/rank class)              |
| `directorium.get_mass_names_for_month(year, month, ...)`     | `list[MassName]` | `MassName` for every day of a month                                       |
| `directorium.get_mass_names_for_year(year, ...)`             | `list[MassName]` | `MassName` for every day of a year                                        |

### Mass propers and assembly

| Function                                                         | Returns    | Description                                                      |
|------------------------------------------------------------------|------------|------------------------------------------------------------------|
| `directorium.get_mass_day(dt, config, tabulae_path, missa_path)` | `MassDay`  | Full occurrence resolution + resolved document AST               |
| `assembly.assemble_mass(propers, config, missa_path, ordo?)`     | `Document` | Combine Ordo template with resolved propers into a complete Mass |

### Parsing and resolution

| Function                                   | Returns    | Description                                                     |
|--------------------------------------------|------------|-----------------------------------------------------------------|
| `parser.parse(text)`                       | `Document` | Parse a raw text string into a Document AST                     |
| `parser.parse_file(path)`                  | `Document` | Parse a `.txt` file into a Document AST                         |
| `resolver.resolve(doc, config, base_path)` | `Document` | 8-phase resolution: conditions, @-refs, $-macros, &-subroutines |
| `resolver.vero(condition, config)`         | `bool`     | Evaluate a Latin rubric condition (e.g., `"rubrica 1960"`)      |

### Canonical hours

| Function                                                            | Returns       | Description                                   |
|---------------------------------------------------------------------|---------------|-----------------------------------------------|
| `horae.get_horae(date, lat, lng, tz, include_prime?, matins_mode?)` | `HoraeResult` | All 8 canonical hours for a date and location |

### Scripture

| Function                             | Returns                       | Description                                                 |
|--------------------------------------|-------------------------------|-------------------------------------------------------------|
| `scriptura.parse_citation(raw)`      | `NormalizedReference \| None` | Parse a Vulgate citation string into a structured reference |
| `scriptura.lookup_book(abbr)`        | `Book \| None`                | Look up a `Book` enum by abbreviation, name, or OSIS ID     |
| `scriptura.book_name(book, locale?)` | `str`                         | Localised book name (17 locales)                            |

### Frontend options

| Function                                      | Returns              | Description                                                                                        |
|-----------------------------------------------|----------------------|----------------------------------------------------------------------------------------------------|
| `options.get_mass_options()`                  | `MassOptions`        | All user-configurable options (rubrics, mass types, orders, languages, votives, communes, ordines) |
| `options.get_languages_from_disk(missa_path)` | `tuple[Option, ...]` | Discover available languages by scanning the `missa/` directory                                    |

### Key types

| Type                  | Module                        | Description                                                                            |
|-----------------------|-------------------------------|----------------------------------------------------------------------------------------|
| `MissalConfig`        | `sacrum.captator.resolver`    | Central frozen dataclass: rubric, mass type, order, language, temporal context         |
| `Rubric`              | `sacrum.captator.resolver`    | Enum: `TRIDENT_1570`, `TRIDENT_1910`, `TRIDENT_1930`, `RUBRICAE_1955`, `RUBRICAE_1960` |
| `MassType`            | `sacrum.captator.resolver`    | Enum: `SOLEMN`, `READ`, `REQUIEM`                                                      |
| `OrderVariant`        | `sacrum.captator.resolver`    | Enum: `ROMAN`, `MONASTIC`, `DOMINICAN`, `CISTERCIAN`                                   |
| `MassInfo`            | `sacrum.captator.directorium` | Date + name + canonical name + rank + rank_name + colour + commemorations              |
| `MassName`            | `sacrum.captator.directorium` | Lighter: name + canonical name + rank + commemorations                                 |
| `MassDay`             | `sacrum.captator.directorium` | Full result: occurrence + resolved document AST                                        |
| `OccurrenceResult`    | `sacrum.captator.directorium` | Winner file, rank, names, commemorations, BVM Saturday, Requiem flags                  |
| `LiturgicalColor`     | `sacrum.captator.directorium` | Enum: `WHITE`, `RED`, `GREEN`, `VIOLET`, `BLACK`, `ROSE`                               |
| `Document`            | `sacrum.captator.parser`      | Parsed AST: preamble + list of sections                                                |
| `Section`             | `sacrum.captator.parser`      | AST section: header + body lines                                                       |
| `HoraeResult`         | `horae`                       | Sunrise, sunset, 8 canonical hours, temporal hour durations                            |
| `HoraCanonica`        | `horae`                       | Single hour: name, start, end, duration, Roman hour, day/night flag                    |
| `NormalizedReference` | `scriptura`                   | Parsed citation: book, chapter, verse range, verse IDs                                 |
| `Book`                | `scriptura`                   | IntEnum: 73 books of the Vulgate canon                                                 |

## Supported rubrical editions

| Enum value             | Edition                                    | Year  |
|------------------------|--------------------------------------------|-------|
| `Rubric.TRIDENT_1570`  | Original Tridentine (Pius V)               | 1570  |
| `Rubric.TRIDENT_1910`  | Divino Afflatu (Pius X)                    | 1911  |
| `Rubric.TRIDENT_1930`  | Post-Divino Afflatu (Pius XI)              | ~1930 |
| `Rubric.RUBRICAE_1955` | Simplified rubrics (Pius XII)              | 1955  |
| `Rubric.RUBRICAE_1960` | Code of Rubrics / 1962 Missal (John XXIII) | 1960  |

Each edition affects the liturgical calendar (which feasts exist, their
ranks, octaves, vigils), the temporal file variants used, and the
evaluation of `(rubrica ...)` conditions within the documents.

## Liturgical colours

The `LiturgicalColor` enum represents the six vestment colours of the
Roman Rite.  Colours are determined algorithmically from the Latin feast
name (ported from the Perl `liturgical_color()` function in Divinum
Officium), plus special detection for Gaudete and Laetare Sundays.

| Value    | Vestments | When used                                                             |
|----------|-----------|-----------------------------------------------------------------------|
| `WHITE`  | White     | Christmas, Easter, Confessors, Virgins, Our Lady, Angels, Dedications |
| `RED`    | Red       | Pentecost, Martyrs, Apostles, Evangelists, Holy Cross, Precious Blood |
| `GREEN`  | Green     | Sundays and ferias after Epiphany and after Pentecost (Ordinary Time) |
| `VIOLET` | Violet    | Advent, Lent, Passiontide, Vigils, Ember Days, Rogation Days          |
| `BLACK`  | Black     | Masses for the Dead (Requiem), Good Friday                            |
| `ROSE`   | Rose      | Gaudete Sunday (Advent III) and Laetare Sunday (Lent IV)              |

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
  options.  The available choices are listed by `get_mass_options()`
  but the Directorium does not yet apply them when resolving a day.
