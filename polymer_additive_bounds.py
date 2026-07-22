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
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class StockParameters:
    polymer_stock_wt_percent: float = 21.0
    additive_stock_polymer_wt_percent: float = 21.0
    additive_stock_additive_wt_percent: float = 4.0


DEFAULT_STOCKS = StockParameters()


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


def _point_in_triangle(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    b1 = _sign(p, a, b) >= 0.0
    b2 = _sign(p, b, c) >= 0.0
    b3 = _sign(p, c, a) >= 0.0
    return (b1 == b2) and (b2 == b3)


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


def _closest_point_in_triangle(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> tuple[float, float]:
    if _point_in_triangle(p, a, b, c):
        return p

    candidates = [
        _closest_point_on_segment(p, a, b),
        _closest_point_on_segment(p, b, c),
        _closest_point_on_segment(p, c, a),
        a,
        b,
        c,
    ]

    best = candidates[0]
    best_d2 = _dist2(p, best)

    for q in candidates[1:]:
        d2 = _dist2(p, q)
        if d2 < best_d2:
            best = q
            best_d2 = d2

    return best


def closest_feasible_target(
    target_polymer_wt_percent: float,
    target_additive_wt_percent: float,
    stocks: StockParameters = DEFAULT_STOCKS,
) -> tuple[float, float]:
    """
    Return the closest feasible target as (polymer_wt_percent, additive_wt_percent).
    """

    v_normal = (stocks.polymer_stock_wt_percent, 0.0)
    v_additive = (
        stocks.additive_stock_polymer_wt_percent,
        stocks.additive_stock_additive_wt_percent,
    )
    v_solvent = (0.0, 0.0)

    requested = (float(target_polymer_wt_percent), float(target_additive_wt_percent))
    corrected = _closest_point_in_triangle(requested, v_normal, v_additive, v_solvent)

    return corrected[0], corrected[1]


def get_composition_bounds(stocks: StockParameters = DEFAULT_STOCKS) -> dict:
    """
    Return the feasible composition region from stock parameters alone.

    The feasible region is a triangle with vertices:
        (polymer_stock_wt_percent, 0)
        (additive_stock_polymer_wt_percent, additive_stock_additive_wt_percent)
        (0, 0)

    Returns a dict with:
        vertices   — list of (polymer_wt, additive_wt) triangle corners
        polymer_wt_max  — max achievable polymer wt%
        additive_wt_max — max achievable additive wt%
    """
    return {
        "vertices": [
            (stocks.polymer_stock_wt_percent, 0.0),
            (stocks.additive_stock_polymer_wt_percent, stocks.additive_stock_additive_wt_percent),
            (0.0, 0.0),
        ],
        "polymer_wt_max": max(stocks.polymer_stock_wt_percent, stocks.additive_stock_polymer_wt_percent),
        "additive_wt_max": stocks.additive_stock_additive_wt_percent,
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
    p, a = test_target(11.0, 44)
    print(p, a)
    print(get_composition_bounds())