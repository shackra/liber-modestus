"""Document resolver for Divinum Officium Missa files.

This module takes a parsed ``Document`` and a ``MissalConfig``, then:

1. Evaluates rubric conditions (``(rubrica ...)``, ``(sed ...)``, etc.)
   to select the correct variants for the chosen edition.
2. Resolves ``@``-cross-references by loading referenced files and
   inlining their content.
3. Filters display markers (``!*S``, ``!*R``, ``!*D``, etc.) based on
   the Mass type (solemn/read/requiem).
4. Processes inline conditionals with backward/forward scoping.

The result is a *resolved* ``Document`` ready for presentation.

Usage::

    from captator.parser import parse_file
    from captator.resolver import MissalConfig, Rubric, MassType, resolve

    config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
    doc = parse_file("path/to/Sancti/01-06.txt")
    resolved = resolve(doc, config, base_path="path/to/missa/Latin")
"""

from .config import MassType, MissalConfig, OrderVariant, Rubric
from .evaluator import vero
from .resolve import resolve

__all__ = [
    "MassType",
    "MissalConfig",
    "OrderVariant",
    "Rubric",
    "resolve",
    "vero",
]
