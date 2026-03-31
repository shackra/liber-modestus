"""Horae -- canonical hours calculator using temporal (unequal) hours.

The traditional Roman system divides daytime (sunrise to sunset) and
nighttime (sunset to next sunrise) each into 12 equal *temporal* hours
whose absolute length varies with the season and geographic location.
"""

from .calc import HoraCanonica, HoraeResult, MatinsMode, get_horae

__all__ = ["HoraCanonica", "HoraeResult", "MatinsMode", "get_horae"]
