"""PFM package — importing it registers every Path Finding Module."""

from __future__ import annotations

from .base import PFM, REGISTRY, get, list_pfms, register
from . import families  # noqa: F401  registers voronoi/lbg/adaptive x styles
from . import grid      # noqa: F401  registers grid halftone + random stipple

__all__ = ["PFM", "REGISTRY", "get", "list_pfms", "register"]
