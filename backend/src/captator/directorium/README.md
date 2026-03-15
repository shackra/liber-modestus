# captator.directorium

Liturgical calendar engine for the traditional Roman Mass.  Given a
calendar date and a `MissalConfig`, determines which Mass propers to use
by resolving the temporal cycle, sanctoral calendar, year-dependent
transfers, and occurrence (precedence) rules.

## How it works

```
         date + MissalConfig
               |
     +---------+---------+
     |                   |
     v                   v
 Temporal cycle    Sanctoral Kalendar
 (date -> ID)      (date -> feast)
     |                   |
     v                   v
 Tempora table     Transfer table
 (remap files)     (year-dependent)
     |                   |
     +--------+----------+
              |
              v
        Occurrence
        (who wins?)
              |
              v
          MassDay
   (winner, commemorations,
    resolved Document)
```

### Step by step

1. **Temporal cycle**: Converts the date to a Tempora ID such as
   `Adv1-0` (First Sunday of Advent), `Quad6-4` (Holy Thursday),
   `Pasc0-0` (Easter Sunday), or `Pent14-3` (Wednesday of the 14th
   week after Pentecost).

2. **Tempora remapping**: The Tempora ID is looked up in the edition's
   Tempora table.  Different editions use different file variants --
   for example, `Tempora/Adv1-0` maps to `Tempora/Adv1-0o` in the
   Tridentine edition, while `Tempora/Quad6-0` maps to
   `Tempora/Quad6-0r` (reformed Holy Week) in 1960.

3. **Sanctoral Kalendar**: The date is looked up in the edition's
   Kalendar (built by layering inheritance: 1570 -> 1888 -> ... ->
   1960).  Returns the saint's feast for that date, its rank, and any
   commemorations.

4. **Transfers**: Year-dependent feast transfers are loaded from the
   Transfer tables, selected by the dominical letter and Easter date of
   the year.  Entries are filtered by the edition's version stems.
   This is how movable feasts like **Christ the King** (last Sunday of
   October) are placed on the correct date.

5. **Occurrence**: Compares the temporal and sanctoral ranks to
   determine which office wins.  The loser (if any) becomes a
   commemoration.  Includes edition-specific rank adjustments (e.g.,
   pre-Divino minor Sundays have reduced rank).

6. **Resolution**: The winning file is parsed and resolved through the
   `captator.resolver` pipeline, producing a fully resolved `Document`
   AST.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Public API: `get_mass_day()`, `MassDay`, temporal cycle, version mapping |
| `tables.py` | Tabulae loaders: `data.txt`, Kalendaria, Tempora, Transfer (with inheritance and version filtering) |
| `occurrence.py` | Occurrence resolution: temporal vs sanctoral precedence, BVM Saturday, Requiem detection |

## Usage

### Get the Mass for a specific date

```python
from datetime import date
from captator.directorium import get_mass_day
from captator.resolver import MissalConfig, Rubric

config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
day = get_mass_day(
    date(2025, 10, 26),
    config,
    tabulae_path="path/to/Tabulae",
    missa_path="path/to/missa/Latin",
)

print(day.occurrence.winner_file)       # 'Sancti/10-DUr' (Christ the King)
print(day.occurrence.winner_name)       # '(transferred)'
print(day.occurrence.is_sanctoral)      # True
print(day.occurrence.commemorations)    # ['Tempora/Pent20-0']
```

### Compare editions for the same date

```python
from datetime import date
from captator.directorium import get_mass_day
from captator.resolver import MissalConfig, Rubric

tabulae = "path/to/Tabulae"
missa = "path/to/missa/Latin"
dt = date(2025, 1, 7)

day_1960 = get_mass_day(dt, MissalConfig(rubric=Rubric.RUBRICAE_1960), tabulae, missa)
day_trid = get_mass_day(dt, MissalConfig(rubric=Rubric.TRIDENT_1570), tabulae, missa)

print(f"1960: {day_1960.occurrence.winner_file}")
# 'Tempora/Epi1-2' (ordinary feria, octave suppressed)

print(f"Trid: {day_trid.occurrence.winner_file}")
# 'Sancti/01-07' (Second day within the Octave of Epiphany)
```

### Check the MassDay fields

```python
day = get_mass_day(date(2025, 3, 19), config, tabulae, missa)

day.date                    # datetime.date(2025, 3, 19)
day.tempora_id              # 'Quad2-3' (Wednesday of Lent week 2)
day.tempora_file            # 'Tempora/Quad2-3'
day.sanctoral_date          # '03-19'
day.occurrence.winner_file  # 'Sancti/03-19' (St Joseph wins)
day.occurrence.winner_rank  # 6.0 (I classis)
day.occurrence.is_sanctoral # True
day.occurrence.commemorations     # ['Tempora/Quad2-3']
day.occurrence.is_bmv_saturday    # False
day.occurrence.is_requiem         # False
day.resolved_document       # Document AST, fully resolved
```

## Edition differences

What changes between rubrical editions:

| Aspect | Tridentine (1570) | 1962 Missal (1960) |
|--------|-------------------|--------------------|
| Tempora files | `Adv1-0o`, `Quad2-0t`, `Pent02-0o` | `Adv1-0`, `Quad6-0r` (reformed Holy Week) |
| Epiphany Octave | Full octave: `Sancti/01-07` through `01-13` | Suppressed (ordinary ferias) |
| Minor Sunday rank | 2.9 (any Duplex saint wins) | 5.0 (II classis, protected) |
| Christ the King | Does not exist (pre-1925) | `Sancti/10-DUr`, last Sunday of October |
| Vigils | All present (24+ vigils) | Only Christmas, Assumption, Pentecost |
| Octaves | Numerous (Epiphany, St John Baptist, Sts Peter & Paul, St Lawrence, Assumption, All Saints, etc.) | Only Christmas, Easter, Pentecost |
| Feast ranking | Duplex I cl., Duplex II cl., Duplex majus, Duplex, Semiduplex, Simplex | Classes I-IV |
| Kalendar size | 223 base entries | Inherited with 38 override entries |

## Automatic features

### BVM Saturday (Missa S. Mariae in Sabbato)

Automatically assigned when all conditions are met:
- It is Saturday (`day_of_week == 6`)
- The temporal rank is below 1.4 (no privileged feria)
- The sanctoral rank is below 1.4 (no feast)
- No transferred vigil occupies the day

The commune variant is selected by liturgical season:

| Season | Commune |
|--------|---------|
| Advent | `C10a` |
| Nativity to Purification | `C10b` |
| Epiphany / Lent | `C10c` |
| Paschaltide | `C10Pasc` |
| Pentecost to Advent | `C10` |

### Requiem (All Souls, November 2)

When the sanctoral winner has "Defunctorum" in its feast name, the
`is_requiem` flag is set to `True`.  This happens automatically on
November 2 (Commemoratio Omnium Fidelium Defunctorum) when it does not
fall on a Sunday.  When it falls on a Sunday, the Sunday wins and All
Souls is commemorated.

### Christ the King (last Sunday of October)

A movable feast handled via the Transfer files.  The dominical letter of
the year determines which October date (25-31) maps to `Sancti/10-DU`
or `Sancti/10-DUr` (reformed variant).

The Transfer file version filters ensure the feast only appears for
editions from Divino Afflatu (post-1925) onward.  Pre-1925 editions
(1570, 1888, 1906) do not include it.

## Tabulae data format reference

The Directorium reads its configuration from text files in the
`Tabulae/` directory of the Divinum Officium data:

### data.txt

CSV mapping version names to file stems and inheritance:

```
version,kalendar,transfer,stransfer,base,transferbase
Tridentine - 1570,1570,1570,1570
Rubrics 1960 - 1960,1960,1960,1960,Reduced - 1955
```

### Kalendaria/\<stem\>.txt

Saints calendar per edition.  Each line: `MM-DD=fileref[~comm]=Name=rank=`

```
01-06=01-06=Epiphaniae Domini=6=
01-14=01-14~01-14cc=S. Hilarii=3=S. Felicis=1=
```

Derived editions only list changes from their base (delta format).

### Tempora/\<stem\>.txt

Temporal file remapping.  Each line: `TemporalKey=ReplacementFile;;`

```
Tempora/Quad6-0=Tempora/Quad6-0r;;
Tempora/Adv1-0=Tempora/Adv1-0o;;
```

`XXXXX` = suppressed (temporal day does not exist in this edition).

### Transfer/\<letter|easter\>.txt

Year-dependent feast transfers.  Each line: `MM-DD=fileref[;;version_filter]`

```
10-25=10-DU;;DA M1930 M1963 C1951 CAV
10-25=10-DUr;;1960 Newcal
```

Files are selected by the dominical letter (`a`-`g`) and Easter date
(`322`-`426`) of the year.  Version filters ensure entries only apply to
their intended editions.

## Current limitations

- **Temporal rank estimation** uses a heuristic instead of parsing the
  actual `[Rank]` section.  Ember Days and unusual vigils may get
  incorrect ranks.
- **Transfer rank estimation** uses a lookup table for known high-rank
  feasts (Christ the King).  Unknown transfers default to rank 5.0.
- **Concurrence** (Vespers conflict) is not implemented -- only needed
  for the Divine Office.
- **Votive Masses** and **daily Requiem** are user-selected and not yet
  exposed through the Directorium API.
- **Anticipated Sundays** (Sundays transferred to Saturday in the
  Tridentine breviary) are not handled.
