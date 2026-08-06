#!/usr/bin/env python3
"""
Target bounds tester / corrector for the polymer-additive mixing system.

Input:
    target_polymer_wt_percent
    target_additive_wt_percent

Output:
    corrected_polymer_wt_percent, corrected_additive_wt_percent

Behavior:
    - If the requested target is already feasible, return it unchanged.
    - If it is outside the feasible region, return the closest feasible target.

Feasible region:
    Triangle with vertices:
        (polymer_stock_wt_percent, 0)
        (additive_stock_polymer_wt_percent, additive_stock_additive_wt_percent)
        (0, 0)

For the current system this is:
    (21, 0), (21, 4), (0, 0)

A fourth bottle (pure additive, no polymer) is planned but not physically in the lab yet --
StockParameters already carries its composition (no_polymer_polymer_wt_percent /
no_polymer_additive_wt_percent), but USE_FOURTH_BOTTLE below stays False until it exists. Once
True, the feasible region becomes the quadrilateral (21, 0), (21, 4), (0, 8), (0, 0) instead of
the triangle -- the point-in-region/closest-point math already generalizes to either shape.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class StockParameters:
    polymer_stock_wt_percent: float = 17.0
    additive_stock_polymer_wt_percent: float = 17.0
    additive_stock_additive_wt_percent: float = 4.0
    # fourth bottle -- not physically available yet, see USE_FOURTH_BOTTLE below
    #no_polymer_polymer_wt_percent: float = 0.0
    #no_polymer_additive_wt_percent: float = 8.0


DEFAULT_STOCKS = StockParameters()

# Set True once the fourth bottle (pure additive, no polymer) physically exists in the lab --
# switches the feasible region from a triangle to a quadrilateral. False = unchanged 3-bottle
# behavior (StockParameters' no_polymer_* fields are ignored).
USE_FOURTH_BOTTLE = False


def send_metadata(stocks: StockParameters = DEFAULT_STOCKS) -> dict:
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


def _stock_vertices(stocks: StockParameters) -> list[tuple[float, float]]:
    """Feasible-region vertices in winding order. Triangle by default; USE_FOURTH_BOTTLE
    inserts the no-polymer additive stock as a 4th vertex, turning it into a quadrilateral."""
    vertices = [
        (stocks.polymer_stock_wt_percent, 0.0),
        (stocks.additive_stock_polymer_wt_percent, stocks.additive_stock_additive_wt_percent),
    ]
    if USE_FOURTH_BOTTLE:
        vertices.append((stocks.no_polymer_polymer_wt_percent, stocks.no_polymer_additive_wt_percent))
    vertices.append((0.0, 0.0))
    return vertices


def closest_feasible_target(
    target_polymer_wt_percent: float,
    target_additive_wt_percent: float,
    stocks: StockParameters = DEFAULT_STOCKS,
) -> tuple[float, float]:
    """
    Return the closest feasible target as (polymer_wt_percent, additive_wt_percent).
    """
    requested = (float(target_polymer_wt_percent), float(target_additive_wt_percent))
    corrected = _closest_point_in_polygon(requested, _stock_vertices(stocks))

    return corrected[0], corrected[1]


def get_composition_bounds(stocks: StockParameters = DEFAULT_STOCKS) -> dict:
    """
    Return the feasible composition region from stock parameters alone.

    The feasible region is a triangle (or, with USE_FOURTH_BOTTLE, a quadrilateral) --
    see _stock_vertices().

    Returns a dict with:
        vertices   — list of (polymer_wt, additive_wt) region corners
        polymer_wt_max  — max achievable polymer wt%
        additive_wt_max — max achievable additive wt%
    """
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
    p, a = test_target(11.0, 44)
    print(p, a)
    print(get_composition_bounds())