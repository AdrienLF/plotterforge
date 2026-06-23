"""Register the sampler-family x style PFM matrix (~21 modules)."""

from __future__ import annotations

from .base import PFM, register
from ._params import (
    FAMILY_LABELS,
    SAMPLER_PARAMS,
    SEED,
    STYLE_LABELS,
    STYLE_ORDER,
    style_params,
)


def _build() -> None:
    for family in ("voronoi", "lbg", "adaptive"):
        sampler = SAMPLER_PARAMS[family]
        for style in STYLE_ORDER:
            params = SEED + sampler + style_params(style)
            # de-dupe by name (e.g. a style could re-declare a sampler key)
            seen: dict[str, object] = {}
            for p in params:
                seen[p.name] = p
            register(PFM(
                id=f"{family}_{style}",
                name=f"{FAMILY_LABELS[family]} {STYLE_LABELS[style]}",
                family=family,
                style=style,
                params=list(seen.values()),
            ))


_build()
