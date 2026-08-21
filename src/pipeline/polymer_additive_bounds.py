#!/usr/bin/env python3
"""
Target bounds tester / corrector for the polymer-additive mixing system.

Input:
    target_polymer_wt_percent
    target_additive_wt_percent (== cosolvent wt%)

Output:
    corrected_polymer_wt_percent, corrected_additive_wt_percent

Behavior:
    - If the requested target is already feasible, return it unchanged.
    - If it is outside the feasible region, return the closest feasible target.

Stock structure (StockParameters, current):
    Bottle 1 - polymer stock:   polymer + solvent            -> (polymer_stock_pwt, 0)
    Bottle 2 - cosolvent stock: cosolvent + solvent           -> (0, solvents_cswt)
    Bottle 3 - all-mix stock:   polymer + solvent + cosolvent -> (all_mix_pwt, all_mix_cswt)
    Bottle 4 - pure solvent (just solvent -- always available) -> (0, 0)

Feasible region:
    Quadrilateral over all 4 bottles -- pure solvent is always available for dilution, same as
    it always was for the legacy structure's (0, 0) vertex, so it's never gated behind a flag.

For the current system this is:
    (17, 0), (17, 24.9), (0, 30), (0, 0)

Legacy structure (OldStockStruct, pre-cosolvent-bottle):
    Bottle 1 - polymer stock:   polymer + solvent            -> (polymer_stock_wt_percent, 0)
    Bottle 2 - additive stock:  polymer + solvent + additive  -> (additive_stock_polymer_wt_percent,
                                                                   additive_stock_additive_wt_percent)
    Solvent dilution down to (0, 0) always assumed available (no separate cosolvent bottle).

USE_NEW_STOCK_STRUCTURE picks which of the two struct shapes is active. This is temporary
scaffolding for the changeover, not meant to stay a permanent toggle -- flip it back to False
if the new cosolvent-bottle math needs to be backed out.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

#in any mix with cosolvent and solvent, there's this amt of cosolvent
#for each unit of solvent. NOT incluidng polymer
cosolvent_frac = 0.70


@dataclass
class OldStockStruct:
    polymer_stock_wt_percent: float = 17.0
    additive_stock_polymer_wt_percent: float = 17.0
    additive_stock_additive_wt_percent: float = 4.0


@dataclass
class StockParameters:
    #first bottle - polymer + solvent
    polymer_stock_pwt: float = 17.0
    #second bottle - cosolvent + solvent
    solvents_cswt: float = cosolvent_frac*100
    #third bottle - polymer + solvent + cosolvent
    all_mix_pwt: float = 17.0
    all_mix_cswt: float = (100-all_mix_pwt)*cosolvent_frac
    # fourth bottle is pure solvent, whose composition is always (0, 0)


# Temporary switch for the cosolvent-bottle changeover -- True = new StockParameters (4 bottles,
# cosolvent stock is real), False = fall back to the old 2-bottle-plus-dilution model
# (OldStockStruct). Flip to False to revert if the new structure needs backing out.
USE_NEW_STOCK_STRUCTURE = True

DEFAULT_STOCKS: StockParameters | OldStockStruct = (
    StockParameters() if USE_NEW_STOCK_STRUCTURE else OldStockStruct()
)


def send_metadata(stocks: StockParameters | OldStockStruct = DEFAULT_STOCKS) -> dict:
    """
    Serialize the stock class into a JSON-safe dict, meant to be attached to the
    params payload sent to the opentrons server (e.g. under a "stock_metadata" key)
    so volume calculations there can eventually read it.
    """
    return asdict(stocks)


def _dot(u: tuple[float, float], v: tuple[float, float]) -> float:
    return u[0] * v[0] + u[1] * v[1]


def _sub(u: tuple[float, float], v: tuple[float, float]) -> tuple[float, float]:
    return (u[0] - v[0], u[1] - v[1])


def _add(u: tuple[float, float], v: tuple[float, float]) -> tuple[float, float]:
    return (u[0] + v[0], u[1] + v[1])


def _scale(u: tuple[float, float], s: float) -> tuple[float, float]:
    return (u[0] * s, u[1] * s)


def _sign(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> float:
    return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])


def _point_in_polygon(
    p: tuple[float, float],
    vertices: list[tuple[float, float]],
) -> bool:
    """Convex-polygon point test: same-sign cross product on every edge. vertices must be
    listed in a consistent winding order (CW or CCW) -- reduces to the old triangle test
    when given exactly 3 points."""
    n = len(vertices)
    signs = [_sign(p, vertices[i], vertices[(i + 1) % n]) >= 0.0 for i in range(n)]
    return all(s == signs[0] for s in signs)


def _closest_point_on_segment(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> tuple[float, float]:
    ab = _sub(b, a)
    denom = _dot(ab, ab)

    if denom == 0.0:
        return a

    t = _dot(_sub(p, a), ab) / denom
    t = max(0.0, min(1.0, t))
    return _add(a, _scale(ab, t))


def _dist2(p: tuple[float, float], q: tuple[float, float]) -> float:
    dx = p[0] - q[0]
    dy = p[1] - q[1]
    return dx * dx + dy * dy


def _closest_point_in_polygon(
    p: tuple[float, float],
    vertices: list[tuple[float, float]],
) -> tuple[float, float]:
    """Closest point inside a convex polygon (or on its boundary). Reduces to the old
    triangle behavior when given exactly 3 vertices."""
    if _point_in_polygon(p, vertices):
        return p

    n = len(vertices)
    candidates = [
        _closest_point_on_segment(p, vertices[i], vertices[(i + 1) % n]) for i in range(n)
    ] + list(vertices)

    best = candidates[0]
    best_d2 = _dist2(p, best)

    for q in candidates[1:]:
        d2 = _dist2(p, q)
        if d2 < best_d2:
            best = q
            best_d2 = d2

    return best


def _stock_vertices(stocks: StockParameters | OldStockStruct) -> list[tuple[float, float]]:
    """Feasible-region vertices in winding order, built from whichever stock struct is passed.
    Pure solvent is always available for dilution down to (0, 0) in both -- it's just solvent,
    not something to gate behind a flag.

    StockParameters (new, cosolvent bottle real): quadrilateral from the polymer stock, the
    all-mix stock, the cosolvent stock, and (0, 0).

    OldStockStruct (legacy): triangle from the polymer stock, the additive stock, and (0, 0).
    """
    if isinstance(stocks, StockParameters):
        return [
            (stocks.polymer_stock_pwt, 0.0),
            (stocks.all_mix_pwt, stocks.all_mix_cswt),
            (0.0, stocks.solvents_cswt),
            (0.0, 0.0),
        ]

    return [
        (stocks.polymer_stock_wt_percent, 0.0),
        (stocks.additive_stock_polymer_wt_percent, stocks.additive_stock_additive_wt_percent),
        (0.0, 0.0),
    ]


def closest_feasible_target(
    target_polymer_wt_percent: float,
    target_additive_wt_percent: float,
    stocks: StockParameters | OldStockStruct = DEFAULT_STOCKS,
) -> tuple[float, float]:
    """
    Return the closest feasible target as (polymer_wt_percent, additive_wt_percent).
    """
    requested = (float(target_polymer_wt_percent), float(target_additive_wt_percent))
    corrected = _closest_point_in_polygon(requested, _stock_vertices(stocks))

    return corrected[0], corrected[1]


def get_composition_bounds(stocks: StockParameters | OldStockStruct = None) -> dict:
    """
    Return the feasible composition region from stock parameters alone.

    The feasible region is a triangle (OldStockStruct) or a quadrilateral (StockParameters) --
    see _stock_vertices().

    stocks defaults to None, not DEFAULT_STOCKS directly -- a bound default argument is
    evaluated once at function-definition time, so it would silently ignore any later
    reassignment of the module-level DEFAULT_STOCKS. Looking it up inside the function body
    instead means this always reflects whatever DEFAULT_STOCKS currently is.

    Returns a dict with:
        vertices   — list of (polymer_wt, additive_wt) region corners
        polymer_wt_max  — max achievable polymer wt%
        additive_wt_max — max achievable additive wt%
    """
    if stocks is None:
        stocks = DEFAULT_STOCKS
    vertices = _stock_vertices(stocks)
    return {
        "vertices": vertices,
        "polymer_wt_max": max(v[0] for v in vertices),
        "additive_wt_max": max(v[1] for v in vertices),
    }


def test_target(
    target_polymer_wt_percent: float,
    target_additive_wt_percent: float,
) -> tuple[float, float]:
    """
    Input: two numbers
    Output: two numbers

    Returns the requested target if feasible, otherwise the closest feasible target.
    """
    return closest_feasible_target(
        target_polymer_wt_percent=target_polymer_wt_percent,
        target_additive_wt_percent=target_additive_wt_percent,
        stocks=DEFAULT_STOCKS,
    )


if __name__ == "__main__":
    # Example manual test
    print(send_metadata())
    p, a = test_target(15, 4)
    print(p, a)
    print(get_composition_bounds())
