"""Dip sign convention detection.

Two conventions are both standard in exploration data, and files rarely say
which one they use:

* **signed inclination** -- ``-90`` is straight down, ``0`` is horizontal,
  ``+90`` is straight up. This is what ``compute_minimum_curvature_trace``
  expects, and what the database stores.
* **dip below horizontal** -- ``70`` means "70 degrees below horizontal", i.e.
  downward. Positive numbers, no sign at all.

Feeding the second into a desurvey that assumes the first sends the hole
*upward into the air*, so every interval plots above the collar. The samples
are still at their correct distance along the trajectory -- the trajectory is
just inverted -- which makes it look like a depth-placement bug when it is
really a sign-convention bug.

Detection is deliberately conservative. A DD/RC hole set whose dips are ALL
positive cannot be surface drilling (you cannot drill upward from the surface),
so it is the "below horizontal" convention and gets negated. Anything with a
mix of signs is already signed data and is left untouched.

Trenches (TR/CH/FC) are excluded entirely: there, dip is the local ground slope
at the start point, where a genuine positive value means "uphill" and must be
preserved. See combined_routing.py for that constraint.
"""
from typing import Iterable, List, Optional, Tuple

# Hole types whose dip is a drilling trajectory (as opposed to ground slope).
_DRILLED_TYPES = {"DD", "RC", None, ""}

SIGNED = "signed"                  # -90 = down; leave alone
POSITIVE_DOWN = "positive_down"    # +70 = 70 below horizontal; negate


def detect_dip_convention(
    dips: Iterable[float],
    hole_types: Optional[Iterable[Optional[str]]] = None,
) -> str:
    """Return SIGNED or POSITIVE_DOWN for a set of survey dips.

    Only dips belonging to drilled holes (DD/RC, or an unspecified type) are
    considered. Zero dips are ignored -- a horizontal hole is unsigned either
    way and carries no evidence.
    """
    dip_list = list(dips)
    if hole_types is None:
        types: List[Optional[str]] = [None] * len(dip_list)
    else:
        types = list(hole_types)

    considered = [
        float(d) for d, t in zip(dip_list, types)
        if d is not None
        and (t.upper() if isinstance(t, str) else t) in _DRILLED_TYPES
    ]
    non_zero = [d for d in considered if abs(d) > 1e-9]

    if not non_zero:
        return SIGNED

    # Every drilled hole pointing up is not physically possible for surface
    # drilling, so an all-positive set is the "below horizontal" convention.
    if all(d > 0 for d in non_zero):
        return POSITIVE_DOWN

    return SIGNED


def normalize_dip(dip: float, convention: str) -> float:
    """Convert a dip into the signed convention the desurvey expects."""
    if convention == POSITIVE_DOWN:
        return -abs(float(dip))
    return float(dip)


def normalize_survey_dips(
    surveys: List[dict],
    hole_types: Optional[dict] = None,
) -> Tuple[List[dict], str]:
    """Normalize a batch of ``{'hole_id', 'depth', 'dip', 'azimuth'}`` dicts.

    ``hole_types`` optionally maps hole_id -> type so trenches can be excluded.
    Returns ``(surveys, convention_used)``; the surveys are modified in place.
    """
    types = []
    for s in surveys:
        types.append((hole_types or {}).get(s.get("hole_id")) if hole_types else None)

    convention = detect_dip_convention((s.get("dip") for s in surveys), types)
    if convention == POSITIVE_DOWN:
        for s, t in zip(surveys, types):
            resolved = t.upper() if isinstance(t, str) else t
            if resolved in _DRILLED_TYPES and s.get("dip") is not None:
                s["dip"] = normalize_dip(s["dip"], POSITIVE_DOWN)

    return surveys, convention
