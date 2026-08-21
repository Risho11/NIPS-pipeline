#!/usr/bin/env python3
"""
PrimoSpire / PVP / NMP Mixing Calculator

Calculates the required stock volumes to prepare a target casting dope with specified:
    - target polymer wt%
    - target additive (cosolvent) wt%
    - target total volume

Two stock structures are supported, matching polymer_additive_bounds.USE_NEW_STOCK_STRUCTURE
(single source of truth for which is active -- import it rather than re-deciding here):

New structure (USE_NEW_STOCK_STRUCTURE=True):
    Polymer stock:    PrimoSpire + NMP
    Cosolvent stock:  PVP + NMP (no polymer)
    All-mix stock:    PrimoSpire + PVP + NMP
    Pure solvent:     NMP -- always available (just solvent), same as the legacy structure's.

    The four-stock problem is underdetermined, so the quadrilateral is split along the diagonal
    from pure solvent to the all-mix stock. Each recipe therefore uses pure solvent, all-mix,
    and either polymer stock or cosolvent stock. This gives a unique, continuous solution over
    the complete feasible region and uses at most three bottles for any one recipe.

Legacy structure (3 bottles, USE_NEW_STOCK_STRUCTURE=False):
    Normal polymer stock:   PrimoSpire + NMP
    Polymer-additive stock: PrimoSpire + PVP + NMP
    Pure solvent:           NMP

All wt% values are with respect to the total mass of the corresponding solution.
For example, an all-mix/polymer-additive stock of:
    21 wt% PrimoSpire + 5 wt% PVP
means:
    21 wt% PrimoSpire
     5 wt% PVP
    74 wt% NMP

Author: generated for lab mixing calculations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
import argparse
import csv
import math

# Composition fields come from polymer_additive_bounds.py -- single source of truth, including
# which stock structure is active (USE_NEW_STOCK_STRUCTURE). Extended here with the density
# fields this file's volume/mass calculations need, which polymer_additive_bounds.py has no
# reason to know about (it's composition/bounds only).
from polymer_additive_bounds import (
    OldStockStruct as _LegacyCompositionStockParameters,
    StockParameters as _NewCompositionStockParameters,
    USE_NEW_STOCK_STRUCTURE,
)


@dataclass
class LegacyStockParameters(_LegacyCompositionStockParameters):
    """Legacy 3-bottle stock (polymer / polymer-additive / pure solvent) + density."""
    polymer_stock_density: float = 1.10
    additive_stock_density: float = 1.12
    solvent_density: float = 1.028  # approximate NMP density near room temperature


@dataclass
class StockParameters(_NewCompositionStockParameters):
    """Four stocks (polymer / solvent-additive / all-mix / solvent) plus densities."""
    polymer_stock_density: float = 1.10
    cosolvent_stock_density: float = 1.03
    all_mix_stock_density: float = 1.12
    solvent_density: float = 1.028  # approximate NMP density near room temperature


# Which stock class is active -- mirrors polymer_additive_bounds.USE_NEW_STOCK_STRUCTURE so
# there's one place deciding this, not two. A different class (and different mass-balance
# solve, see calculate_mix) is sent to the opentrons server depending on which is active.
# Temporary until the 4-bottle system is fully implemented -- not meant to stay a toggle.
ActiveStockParameters = StockParameters if USE_NEW_STOCK_STRUCTURE else LegacyStockParameters
DEFAULT_STOCKS = ActiveStockParameters()


@dataclass
class TargetRecipe:
    """
    Target final casting solution.

    Units:
        total_volume_uL = final dope volume in microliters
        wt%             = percent by total final dope mass
    """
    total_volume_uL: float
    target_polymer_wt_percent: float
    target_additive_wt_percent: float


@dataclass
class LegacyMixingResult:
    """Calculated bottle volumes and final formulation check -- legacy structure."""
    normal_polymer_stock_uL: float
    polymer_additive_stock_uL: float
    solvent_uL: float
    total_volume_uL: float
    final_polymer_wt_percent: float
    final_additive_wt_percent: float
    final_solvent_wt_percent: float


@dataclass
class MixingResult:
    """Calculated bottle volumes and final formulation check -- new structure."""
    polymer_stock_uL: float
    cosolvent_stock_uL: float
    all_mix_stock_uL: float
    solvent_uL: float
    total_volume_uL: float
    final_polymer_wt_percent: float
    final_additive_wt_percent: float
    final_solvent_wt_percent: float


def _det3(m: list[list[float]]) -> float:
    """Determinant of a 3 x 3 matrix."""
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _solve_3x3(a: list[list[float]], b: list[float]) -> tuple[float, float, float]:
    """
    Solve a 3 x 3 linear system using Cramer's rule.

    This avoids requiring numpy, so the file can run on a robot controller
    with only the Python standard library.
    """
    det_a = _det3(a)
    if abs(det_a) < 1e-12:
        raise ValueError("The formulation equations are singular. Check stock concentrations and target values.")

    solutions = []
    for col in range(3):
        ai = [row[:] for row in a]
        for r in range(3):
            ai[r][col] = b[r]
        solutions.append(_det3(ai) / det_a)

    return solutions[0], solutions[1], solutions[2]


def calculate_mix(
    recipe: TargetRecipe,
    stocks: StockParameters | LegacyStockParameters,
    round_to_uL: bool = True,
    min_volume_tolerance_uL: float = 1e-6,
) -> MixingResult | LegacyMixingResult:
    """Calculate required volumes. Dispatches on stocks' type -- see
    _calculate_mix_new / _calculate_mix_legacy."""
    if isinstance(stocks, StockParameters):
        return _calculate_mix_new(recipe, stocks, round_to_uL, min_volume_tolerance_uL)
    return _calculate_mix_legacy(recipe, stocks, round_to_uL, min_volume_tolerance_uL)


def _calculate_mix_legacy(
    recipe: TargetRecipe,
    stocks: LegacyStockParameters,
    round_to_uL: bool,
    min_volume_tolerance_uL: float,
) -> LegacyMixingResult:
    """
    Bottles:
        Vp = normal polymer stock
        Va = polymer-additive stock
        Vs = pure solvent

    The polymer-additive stock can have a different polymer concentration than
    the normal polymer stock.

    Mass balances:

        polymer from normal stock + polymer from additive stock
            = target polymer fraction * total final mass

        additive from additive stock
            = target additive fraction * total final mass

        Vp + Va + Vs = target final volume

    Concentrations are mass fractions, while the unknowns are volumes.
    Density converts each volume contribution to mass.
    """

    if recipe.total_volume_uL <= 0:
        raise ValueError("Target total volume must be positive.")

    # Convert wt% to fractions.
    cp_target = recipe.target_polymer_wt_percent / 100.0
    ca_target = recipe.target_additive_wt_percent / 100.0

    cp_stock = stocks.polymer_stock_wt_percent / 100.0
    cp_add_stock = stocks.additive_stock_polymer_wt_percent / 100.0
    ca_add_stock = stocks.additive_stock_additive_wt_percent / 100.0

    rho_p = stocks.polymer_stock_density
    rho_a = stocks.additive_stock_density
    rho_s = stocks.solvent_density

    # Basic checks.
    if cp_target < 0 or ca_target < 0:
        raise ValueError("Target polymer and additive wt% cannot be negative.")

    if cp_target + ca_target >= 1:
        raise ValueError("Target polymer wt% + additive wt% must be less than 100 wt%.")

    if cp_stock < 0 or cp_add_stock < 0 or ca_add_stock < 0:
        raise ValueError("Stock wt% values cannot be negative.")

    if cp_stock + 1e-12 < cp_target and cp_add_stock + 1e-12 < cp_target:
        raise ValueError(
            "Target polymer wt% is higher than both polymer-containing stocks. "
            "This cannot be made by dilution."
        )

    if ca_target > 0 and ca_add_stock <= 0:
        raise ValueError("Target additive is nonzero, but additive stock contains no additive.")

    if ca_target > ca_add_stock + 1e-12:
        raise ValueError(
            "Target additive wt% is higher than the additive wt% in the additive stock. "
            "This cannot be made by dilution."
        )

    if min(rho_p, rho_a, rho_s) <= 0:
        raise ValueError("All densities must be positive.")

    # Unknown vector x = [Vp, Va, Vs]
    #
    # Polymer balance:
    # cp_stock*rho_p*Vp + cp_add_stock*rho_a*Va
    #     = cp_target * (rho_p*Vp + rho_a*Va + rho_s*Vs)
    #
    # Additive balance:
    # ca_add_stock*rho_a*Va
    #     = ca_target * (rho_p*Vp + rho_a*Va + rho_s*Vs)
    #
    # Volume balance:
    # Vp + Va + Vs = total_volume_uL
    a = [
        [
            (cp_stock - cp_target) * rho_p,
            (cp_add_stock - cp_target) * rho_a,
            -cp_target * rho_s,
        ],
        [
            -ca_target * rho_p,
            (ca_add_stock - ca_target) * rho_a,
            -ca_target * rho_s,
        ],
        [
            1.0,
            1.0,
            1.0,
        ],
    ]
    b = [0.0, 0.0, recipe.total_volume_uL]

    vp, va, vs = _solve_3x3(a, b)

    # Catch impossible formulations.
    raw_volumes = {
        "normal polymer stock": vp,
        "polymer-additive stock": va,
        "solvent": vs,
    }
    negative = {name: vol for name, vol in raw_volumes.items() if vol < -min_volume_tolerance_uL}
    if negative:
        details = ", ".join(f"{name} = {vol:.3f} uL" for name, vol in raw_volumes.items())
        raise ValueError(f"Impossible formulation; calculated a negative volume. {details}")

    # Remove tiny floating-point negatives.
    vp = max(vp, 0.0)
    va = max(va, 0.0)
    vs = max(vs, 0.0)

    if round_to_uL:
        # Round the first two active liquid volumes, then assign the residual to solvent
        # so that the displayed total volume remains exact.
        vp = round(vp)
        va = round(va)
        vs = round(recipe.total_volume_uL - vp - va)

        if vs < -min_volume_tolerance_uL:
            raise ValueError(
                "Rounded volumes made solvent negative. Try round_to_uL=False "
                "or use a larger total volume."
            )

        vs = max(vs, 0.0)

    final = _check_final_composition_legacy(vp, va, vs, stocks)

    return LegacyMixingResult(
        normal_polymer_stock_uL=vp,
        polymer_additive_stock_uL=va,
        solvent_uL=vs,
        total_volume_uL=vp + va + vs,
        final_polymer_wt_percent=final["polymer_wt_percent"],
        final_additive_wt_percent=final["additive_wt_percent"],
        final_solvent_wt_percent=final["solvent_wt_percent"],
    )


def _calculate_mix_new(
    recipe: TargetRecipe,
    stocks: StockParameters,
    round_to_uL: bool,
    min_volume_tolerance_uL: float,
) -> MixingResult:
    """
    Bottles:
        Vp = polymer stock (polymer + solvent, no cosolvent)
        Vc = solvent-additive stock (cosolvent + solvent, no polymer)
        Va = all-mix stock (polymer + solvent + cosolvent)
        Vs = pure solvent

    Mass balances:

        polymer from polymer stock + polymer from all-mix stock
            = target polymer fraction * total final mass

        cosolvent from cosolvent stock + cosolvent from all-mix stock
            = target additive fraction * total final mass

        Vp + Vc + Va = target final volume

    The quadrilateral is split into two triangles along solvent--all-mix. Both candidate
    three-bottle systems are solved; the non-negative candidate identifies the triangle.
    """
    if recipe.total_volume_uL <= 0:
        raise ValueError("Target total volume must be positive.")

    # Convert wt% to fractions.
    cp_target = recipe.target_polymer_wt_percent / 100.0
    ca_target = recipe.target_additive_wt_percent / 100.0

    cp_poly = stocks.polymer_stock_pwt / 100.0
    cc_cosolv = stocks.solvents_cswt / 100.0
    cp_allmix = stocks.all_mix_pwt / 100.0
    cc_allmix = stocks.all_mix_cswt / 100.0

    rho_p = stocks.polymer_stock_density
    rho_c = stocks.cosolvent_stock_density
    rho_a = stocks.all_mix_stock_density
    rho_s = stocks.solvent_density

    # Basic checks.
    if cp_target < 0 or ca_target < 0:
        raise ValueError("Target polymer and additive wt% cannot be negative.")

    if cp_target + ca_target >= 1:
        raise ValueError("Target polymer wt% + additive wt% must be less than 100 wt%.")

    if cp_poly < 0 or cc_cosolv < 0 or cp_allmix < 0 or cc_allmix < 0:
        raise ValueError("Stock wt% values cannot be negative.")

    if cp_poly + 1e-12 < cp_target and cp_allmix + 1e-12 < cp_target:
        raise ValueError(
            "Target polymer wt% is higher than both polymer-containing stocks. "
            "This cannot be made by dilution."
        )

    if ca_target > 0 and cc_cosolv <= 0 and cc_allmix <= 0:
        raise ValueError("Target additive is nonzero, but no stock contains cosolvent.")

    if ca_target > max(cc_cosolv, cc_allmix) + 1e-12:
        raise ValueError(
            "Target additive wt% is higher than any cosolvent-containing stock. "
            "This cannot be made by dilution."
        )

    if min(rho_p, rho_c, rho_a, rho_s) <= 0:
        raise ValueError("All densities must be positive.")

    def solve_triangle(edge_p, edge_c, edge_rho):
        # Unknowns are edge stock, all-mix stock, and pure solvent.
        matrix = [
            [(edge_p - cp_target) * edge_rho, (cp_allmix - cp_target) * rho_a, -cp_target * rho_s],
            [(edge_c - ca_target) * edge_rho, (cc_allmix - ca_target) * rho_a, -ca_target * rho_s],
            [1.0, 1.0, 1.0],
        ]
        return _solve_3x3(matrix, [0.0, 0.0, recipe.total_volume_uL])

    candidates = []
    for edge_name, edge_p, edge_c, edge_rho in (
        ("polymer", cp_poly, 0.0, rho_p),
        ("cosolvent", 0.0, cc_cosolv, rho_c),
    ):
        edge, allmix, solvent = solve_triangle(edge_p, edge_c, edge_rho)
        if min(edge, allmix, solvent) >= -min_volume_tolerance_uL:
            candidates.append((edge_name, max(edge, 0.0), max(allmix, 0.0), max(solvent, 0.0)))

    if not candidates:
        raise ValueError("Impossible formulation; target is outside the four-stock feasible region.")

    edge_name, edge, va, vs = candidates[0]
    vp, vc = (edge, 0.0) if edge_name == "polymer" else (0.0, edge)

    if round_to_uL:
        # Round active stocks and assign the residual to solvent to preserve total volume.
        vp = round(vp)
        vc = round(vc)
        va = round(va)
        vs = round(recipe.total_volume_uL - vp - vc - va)

        if vs < -min_volume_tolerance_uL:
            raise ValueError(
                "Rounded volumes made solvent negative. Try round_to_uL=False "
                "or use a larger total volume."
            )
        vs = max(vs, 0.0)

    final = _check_final_composition_new(vp, vc, va, vs, stocks)

    return MixingResult(
        polymer_stock_uL=vp,
        cosolvent_stock_uL=vc,
        all_mix_stock_uL=va,
        solvent_uL=vs,
        total_volume_uL=vp + vc + va + vs,
        final_polymer_wt_percent=final["polymer_wt_percent"],
        final_additive_wt_percent=final["additive_wt_percent"],
        final_solvent_wt_percent=final["solvent_wt_percent"],
    )


def check_final_composition(
    vol_a_uL: float,
    vol_b_uL: float,
    vol_c_uL: float,
    stocks: StockParameters | LegacyStockParameters,
    solvent_uL: float = 0.0,
) -> dict[str, float]:
    """
    Calculate the final wt% from actual dispensed volumes. Useful after rounding to whole uL.
    Bottle order/meaning depends on which stocks type is passed -- see calculate_mix's
    docstrings (_calculate_mix_new: polymer/cosolvent/all-mix; _calculate_mix_legacy:
    normal-polymer/polymer-additive/solvent).
    """
    if isinstance(stocks, StockParameters):
        return _check_final_composition_new(vol_a_uL, vol_b_uL, vol_c_uL, solvent_uL, stocks)
    return _check_final_composition_legacy(vol_a_uL, vol_b_uL, vol_c_uL, stocks)


def _check_final_composition_legacy(
    normal_polymer_stock_uL: float,
    polymer_additive_stock_uL: float,
    solvent_uL: float,
    stocks: LegacyStockParameters,
) -> dict[str, float]:
    cp_stock = stocks.polymer_stock_wt_percent / 100.0
    cp_add_stock = stocks.additive_stock_polymer_wt_percent / 100.0
    ca_add_stock = stocks.additive_stock_additive_wt_percent / 100.0

    mp = normal_polymer_stock_uL * stocks.polymer_stock_density
    ma = polymer_additive_stock_uL * stocks.additive_stock_density
    ms = solvent_uL * stocks.solvent_density

    total_mass = mp + ma + ms
    if total_mass <= 0:
        raise ValueError("Total mass is zero or negative.")

    polymer_mass = cp_stock * mp + cp_add_stock * ma
    additive_mass = ca_add_stock * ma
    solvent_mass = total_mass - polymer_mass - additive_mass

    return {
        "polymer_wt_percent": 100.0 * polymer_mass / total_mass,
        "additive_wt_percent": 100.0 * additive_mass / total_mass,
        "solvent_wt_percent": 100.0 * solvent_mass / total_mass,
        "total_mass": total_mass,
        "polymer_mass": polymer_mass,
        "additive_mass": additive_mass,
        "solvent_mass": solvent_mass,
    }


def _check_final_composition_new(
    polymer_stock_uL: float,
    cosolvent_stock_uL: float,
    all_mix_stock_uL: float,
    solvent_uL: float,
    stocks: StockParameters,
) -> dict[str, float]:
    cp_poly = stocks.polymer_stock_pwt / 100.0
    cc_cosolv = stocks.solvents_cswt / 100.0
    cp_allmix = stocks.all_mix_pwt / 100.0
    cc_allmix = stocks.all_mix_cswt / 100.0

    mp = polymer_stock_uL * stocks.polymer_stock_density
    mc = cosolvent_stock_uL * stocks.cosolvent_stock_density
    ma = all_mix_stock_uL * stocks.all_mix_stock_density
    ms = solvent_uL * stocks.solvent_density

    total_mass = mp + mc + ma + ms
    if total_mass <= 0:
        raise ValueError("Total mass is zero or negative.")

    polymer_mass = cp_poly * mp + cp_allmix * ma
    additive_mass = cc_cosolv * mc + cc_allmix * ma
    solvent_mass = total_mass - polymer_mass - additive_mass

    return {
        "polymer_wt_percent": 100.0 * polymer_mass / total_mass,
        "additive_wt_percent": 100.0 * additive_mass / total_mass,
        "solvent_wt_percent": 100.0 * solvent_mass / total_mass,
        "total_mass": total_mass,
        "polymer_mass": polymer_mass,
        "additive_mass": additive_mass,
        "solvent_mass": solvent_mass,
    }


def calculate_batch(
    recipes: Iterable[TargetRecipe],
    stocks: StockParameters | LegacyStockParameters,
    round_to_uL: bool = True,
) -> list[MixingResult | LegacyMixingResult]:
    """Calculate a list of target recipes."""
    return [calculate_mix(recipe, stocks, round_to_uL=round_to_uL) for recipe in recipes]


def print_result(recipe: TargetRecipe, result: MixingResult | LegacyMixingResult) -> None:
    """Pretty-print one result."""
    print("\nTarget recipe")
    print("-------------")
    print(f"Total volume:      {recipe.total_volume_uL:.2f} uL")
    print(f"Target polymer:    {recipe.target_polymer_wt_percent:.4g} wt%")
    print(f"Target additive:   {recipe.target_additive_wt_percent:.4g} wt%")

    print("\nRequired volumes")
    print("----------------")
    if isinstance(result, MixingResult):
        print(f"Polymer stock:      {result.polymer_stock_uL:.2f} uL")
        print(f"Cosolvent stock:    {result.cosolvent_stock_uL:.2f} uL")
        print(f"All-mix stock:      {result.all_mix_stock_uL:.2f} uL")
        print(f"Pure solvent:       {result.solvent_uL:.2f} uL")
    else:
        print(f"Normal polymer stock:      {result.normal_polymer_stock_uL:.2f} uL")
        print(f"Polymer-additive stock:    {result.polymer_additive_stock_uL:.2f} uL")
        print(f"Pure solvent:              {result.solvent_uL:.2f} uL")
    print(f"Total:                     {result.total_volume_uL:.2f} uL")

    print("\nFinal composition check")
    print("-----------------------")
    print(f"Polymer:    {result.final_polymer_wt_percent:.4f} wt%")
    print(f"Additive:   {result.final_additive_wt_percent:.4f} wt%")
    print(f"Solvent:    {result.final_solvent_wt_percent:.4f} wt%")


def read_recipes_csv(path: str) -> list[TargetRecipe]:
    """
    Read a CSV file with columns:
        total_volume_uL,target_polymer_wt_percent,target_additive_wt_percent
    """
    recipes = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "total_volume_uL",
            "target_polymer_wt_percent",
            "target_additive_wt_percent",
        }

        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV file is missing columns: {sorted(missing)}")

        for row in reader:
            recipes.append(
                TargetRecipe(
                    total_volume_uL=float(row["total_volume_uL"]),
                    target_polymer_wt_percent=float(row["target_polymer_wt_percent"]),
                    target_additive_wt_percent=float(row["target_additive_wt_percent"]),
                )
            )

    return recipes


def write_results_csv(
    path: str,
    recipes: list[TargetRecipe],
    results: list[MixingResult | LegacyMixingResult],
) -> None:
    """Write batch results to a CSV file. Bottle-volume columns depend on which stock
    structure produced the results (all results in a batch share one structure)."""
    is_new = bool(results) and isinstance(results[0], MixingResult)

    if is_new:
        bottle_fieldnames = ["polymer_stock_uL", "cosolvent_stock_uL", "all_mix_stock_uL", "solvent_uL"]
    else:
        bottle_fieldnames = ["normal_polymer_stock_uL", "polymer_additive_stock_uL", "solvent_uL"]

    fieldnames = [
        "target_total_volume_uL",
        "target_polymer_wt_percent",
        "target_additive_wt_percent",
        *bottle_fieldnames,
        "calculated_total_volume_uL",
        "final_polymer_wt_percent",
        "final_additive_wt_percent",
        "final_solvent_wt_percent",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for recipe, result in zip(recipes, results):
            row = {
                "target_total_volume_uL": recipe.total_volume_uL,
                "target_polymer_wt_percent": recipe.target_polymer_wt_percent,
                "target_additive_wt_percent": recipe.target_additive_wt_percent,
                "calculated_total_volume_uL": result.total_volume_uL,
                "final_polymer_wt_percent": result.final_polymer_wt_percent,
                "final_additive_wt_percent": result.final_additive_wt_percent,
                "final_solvent_wt_percent": result.final_solvent_wt_percent,
            }
            row.update({name: getattr(result, name) for name in bottle_fieldnames})
            writer.writerow(row)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate volumes for polymer / polymer-additive / solvent mixing."
    )

    parser.add_argument("--total-volume-uL", type=float, default=1000.0)
    parser.add_argument("--target-polymer-wt", type=float, default=17.0)
    parser.add_argument("--target-additive-wt", type=float, default=.0)

    if USE_NEW_STOCK_STRUCTURE:
        parser.add_argument("--polymer-stock-pwt", type=float, default=DEFAULT_STOCKS.polymer_stock_pwt)
        parser.add_argument("--solvents-cswt", type=float, default=DEFAULT_STOCKS.solvents_cswt)
        parser.add_argument("--all-mix-pwt", type=float, default=DEFAULT_STOCKS.all_mix_pwt)
        parser.add_argument("--all-mix-cswt", type=float, default=DEFAULT_STOCKS.all_mix_cswt)

        parser.add_argument("--polymer-stock-density", type=float, default=DEFAULT_STOCKS.polymer_stock_density)
        parser.add_argument("--cosolvent-stock-density", type=float, default=DEFAULT_STOCKS.cosolvent_stock_density)
        parser.add_argument("--all-mix-stock-density", type=float, default=DEFAULT_STOCKS.all_mix_stock_density)
        parser.add_argument("--solvent-density", type=float, default=DEFAULT_STOCKS.solvent_density)
    else:
        parser.add_argument("--polymer-stock-wt", type=float, default=DEFAULT_STOCKS.polymer_stock_wt_percent)
        parser.add_argument("--additive-stock-polymer-wt", type=float, default=DEFAULT_STOCKS.additive_stock_polymer_wt_percent)
        parser.add_argument("--additive-stock-additive-wt", type=float, default=DEFAULT_STOCKS.additive_stock_additive_wt_percent)

        parser.add_argument("--polymer-stock-density", type=float, default=DEFAULT_STOCKS.polymer_stock_density)
        parser.add_argument("--additive-stock-density", type=float, default=DEFAULT_STOCKS.additive_stock_density)
        parser.add_argument("--solvent-density", type=float, default=DEFAULT_STOCKS.solvent_density)

    parser.add_argument(
        "--no-round",
        action="store_true",
        help="Do not round calculated volumes to whole uL.",
    )

    parser.add_argument(
        "--input-csv",
        type=str,
        default=None,
        help=(
            "Optional batch input CSV with columns: "
            "total_volume_uL,target_polymer_wt_percent,target_additive_wt_percent"
        ),
    )

    parser.add_argument(
        "--output-csv",
        type=str,
        default=None,
        help="Optional output CSV path for batch results.",
    )

    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    if USE_NEW_STOCK_STRUCTURE:
        stocks = StockParameters(
            polymer_stock_pwt=args.polymer_stock_pwt,
            solvents_cswt=args.solvents_cswt,
            all_mix_pwt=args.all_mix_pwt,
            all_mix_cswt=args.all_mix_cswt,
            polymer_stock_density=args.polymer_stock_density,
            cosolvent_stock_density=args.cosolvent_stock_density,
            all_mix_stock_density=args.all_mix_stock_density,
            solvent_density=args.solvent_density,
        )
    else:
        stocks = LegacyStockParameters(
            polymer_stock_wt_percent=args.polymer_stock_wt,
            additive_stock_polymer_wt_percent=args.additive_stock_polymer_wt,
            additive_stock_additive_wt_percent=args.additive_stock_additive_wt,
            polymer_stock_density=args.polymer_stock_density,
            additive_stock_density=args.additive_stock_density,
            solvent_density=args.solvent_density,
        )

    round_to_uL = not args.no_round

    if args.input_csv:
        recipes = read_recipes_csv(args.input_csv)
        results = calculate_batch(recipes, stocks, round_to_uL=round_to_uL)

        for recipe, result in zip(recipes, results):
            print_result(recipe, result)

        if args.output_csv:
            write_results_csv(args.output_csv, recipes, results)
            print(f"\nWrote batch results to: {args.output_csv}")

    else:
        recipe = TargetRecipe(
            total_volume_uL=args.total_volume_uL,
            target_polymer_wt_percent=args.target_polymer_wt,
            target_additive_wt_percent=args.target_additive_wt,
        )
        result = calculate_mix(recipe, stocks, round_to_uL=round_to_uL)
        print_result(recipe, result)


if __name__ == "__main__":
    main()
