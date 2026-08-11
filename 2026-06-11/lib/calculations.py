from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
import argparse
import csv
import math


@dataclass
class StockParameters:
    """
    Stock solution parameters.

    Units:
        wt%      = percent by total solution mass
        density  = g/mL, g/uL-scaled equivalent, or any consistent mass/volume unit

    The density unit only needs to be consistent across all three liquids.
    """
    polymer_stock_wt_percent: float = 21.0
    additive_stock_polymer_wt_percent: float = 21.0
    additive_stock_additive_wt_percent: float = 5.0
    polymer_stock_density: float = 1.10
    additive_stock_density: float = 1.12
    solvent_density: float = 1.028  # approximate NMP density near room temperature


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
class MixingResult:
    """
    Calculated bottle volumes and final formulation check.
    """
    normal_polymer_stock_uL: float
    polymer_additive_stock_uL: float
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


def _round_volumes_to_target(
    recipe: TargetRecipe,
    stocks: StockParameters,
    vp_exact: float,
    va_exact: float,
    vs_exact: float,
) -> tuple[float, float, float]:
    """Choose whole-uL volumes that best preserve the target polymer/additive wt% after rounding."""
    total_volume_uL = recipe.total_volume_uL
    vp_center = int(round(vp_exact))
    va_center = int(round(va_exact))
    radius = max(5, int(abs(vp_exact - vp_center) + abs(va_exact - va_center) + 2))

    best_choice: Optional[tuple[float, float, float]] = None
    best_score: Optional[float] = None
    best_additive_error: Optional[float] = None

    for vp in range(max(0, vp_center - radius), vp_center + radius + 1):
        for va in range(max(0, va_center - radius), va_center + radius + 1):
            vs = total_volume_uL - vp - va
            if vs < 0:
                continue

            composition = check_final_composition(vp, va, vs, stocks)
            polymer_error = abs(composition["polymer_wt_percent"] - recipe.target_polymer_wt_percent)
            additive_error = abs(composition["additive_wt_percent"] - recipe.target_additive_wt_percent)
            score = polymer_error + additive_error

            if best_choice is None or score < best_score or (
                abs(score - best_score) < 1e-12 and additive_error < best_additive_error
            ):
                best_choice = (float(vp), float(va), float(vs))
                best_score = score
                best_additive_error = additive_error

    if best_choice is None:
        return float(round(vp_exact)), float(round(va_exact)), float(round(vs_exact))

    return best_choice


def calculate_mix(
    recipe: TargetRecipe,
    stocks: StockParameters,
    round_to_uL: bool = True,
    min_volume_tolerance_uL: float = 1e-6,
) -> MixingResult:
    """
    Calculate required volumes for a 3-bottle system.

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

    # No additive in play: target is 0% and the additive stock has none to give.
    # Skip the additive-stock bottle entirely and solve the plain 2-bottle
    # dilution (normal polymer stock + solvent) directly, since the 3x3 system
    # becomes singular (a zero row) in this case.
    if ca_target < 1e-9 and ca_add_stock < 1e-9:
        va = 0.0
        if abs(cp_stock - cp_target) < 1e-12:
            vp = recipe.total_volume_uL
            vs = 0.0
        else:
            denom = (cp_stock - cp_target) * rho_p + cp_target * rho_s
            if abs(denom) < 1e-12:
                raise ValueError(
                    "Cannot solve polymer dilution; check polymer stock/target concentrations."
                )
            vp = (cp_target * rho_s * recipe.total_volume_uL) / denom
            vs = recipe.total_volume_uL - vp
        
    # Simple special case: if both stocks have the same polymer concentration and
    # the same density, the target additive fraction is just a direct dilution of
    # the additive stock. This is the common 10:1 polymer-to-additive case.
    elif (
        abs(rho_p - rho_a) < 1e-12
        and abs(cp_stock - cp_target) < 1e-12
        and abs(cp_add_stock - cp_target) < 1e-12
        and ca_target < ca_add_stock + 1e-12
    ):
        additive_fraction = ca_target / ca_add_stock
        vp = recipe.total_volume_uL * (1.0 - additive_fraction)
        va = recipe.total_volume_uL * additive_fraction
        vs = 0.0
    else:
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
        vp, va, vs = _round_volumes_to_target(recipe, stocks, vp, va, vs)
        if vs < -min_volume_tolerance_uL:
            raise ValueError(
                "Rounded volumes made solvent negative. Try round_to_uL=False "
                "or use a larger total volume."
            )

        vs = max(vs, 0.0)

    final = check_final_composition(vp, va, vs, stocks)

    return MixingResult(
        normal_polymer_stock_uL=vp,
        polymer_additive_stock_uL=va,
        solvent_uL=vs,
        total_volume_uL=vp + va + vs,
        final_polymer_wt_percent=final["polymer_wt_percent"],
        final_additive_wt_percent=final["additive_wt_percent"],
        final_solvent_wt_percent=final["solvent_wt_percent"],
    )


def check_final_composition(
    normal_polymer_stock_uL: float,
    polymer_additive_stock_uL: float,
    solvent_uL: float,
    stocks: StockParameters,
) -> dict[str, float]:
    """
    Calculate the final wt% from actual dispensed volumes.
    Useful after rounding to whole uL.
    """

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


def calculate_batch(
    recipe: TargetRecipe,
    stocks: StockParameters,
    round_to_uL: bool = True,
):
    """Calculate a list of target recipes."""
    return calculate_mix(recipe, stocks, round_to_uL=round_to_uL)


def print_result(recipe: TargetRecipe, result: MixingResult) -> None:
    """Pretty-print one result."""
    print("\nTarget recipe")
    print("-------------")
    print(f"Total volume:      {recipe.total_volume_uL:.2f} uL")
    print(f"Target polymer:    {recipe.target_polymer_wt_percent:.4g} wt%")
    print(f"Target additive:   {recipe.target_additive_wt_percent:.4g} wt%")

    print("\nRequired volumes")
    print("----------------")
    print(f"Normal polymer stock:      {result.normal_polymer_stock_uL:.2f} uL")
    print(f"Polymer-additive stock:    {result.polymer_additive_stock_uL:.2f} uL")
    print(f"Pure solvent:              {result.solvent_uL:.2f} uL")
    print(f"Total:                     {result.total_volume_uL:.2f} uL")

    print("\nFinal composition check")
    print("-----------------------")
    print(f"Polymer:    {result.final_polymer_wt_percent:.4f} wt%")
    print(f"Additive:   {result.final_additive_wt_percent:.4f} wt%")
    print(f"Solvent:    {result.final_solvent_wt_percent:.4f} wt%")

