"""Mass-balance calculations for both supported membrane stock layouts."""
from dataclasses import dataclass


@dataclass
class StockParameters:
    polymer_stock_pwt: float = 17.0
    solvents_cswt: float = 30.0
    all_mix_pwt: float = 17.0
    all_mix_cswt: float = 24.9
    polymer_stock_density: float = 1.10
    cosolvent_stock_density: float = 1.03
    all_mix_stock_density: float = 1.12
    solvent_density: float = 1.028


@dataclass
class LegacyStockParameters:
    polymer_stock_wt_percent: float = 17.0
    additive_stock_polymer_wt_percent: float = 17.0
    additive_stock_additive_wt_percent: float = 4.0
    polymer_stock_density: float = 1.10
    additive_stock_density: float = 1.12
    solvent_density: float = 1.028


@dataclass
class TargetRecipe:
    total_volume_uL: float
    target_polymer_wt_percent: float
    target_additive_wt_percent: float


@dataclass
class MixingResult:
    polymer_stock_uL: float
    cosolvent_stock_uL: float
    all_mix_stock_uL: float
    solvent_uL: float
    total_volume_uL: float
    final_polymer_wt_percent: float
    final_additive_wt_percent: float
    final_solvent_wt_percent: float


@dataclass
class LegacyMixingResult:
    normal_polymer_stock_uL: float
    polymer_additive_stock_uL: float
    solvent_uL: float
    total_volume_uL: float
    final_polymer_wt_percent: float
    final_additive_wt_percent: float
    final_solvent_wt_percent: float


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _solve_3x3(a, b):
    determinant = _det3(a)
    if abs(determinant) < 1e-12:
        raise ValueError("The formulation equations are singular; check stock concentrations.")
    result = []
    for column in range(3):
        replaced = [row[:] for row in a]
        for row in range(3):
            replaced[row][column] = b[row]
        result.append(_det3(replaced) / determinant)
    return tuple(result)


def check_final_composition(vp, vc, va, vs, stocks):
    masses = (vp * stocks.polymer_stock_density, vc * stocks.cosolvent_stock_density,
              va * stocks.all_mix_stock_density, vs * stocks.solvent_density)
    total_mass = sum(masses)
    if total_mass <= 0:
        raise ValueError("Total mass must be positive.")
    polymer_mass = (stocks.polymer_stock_pwt / 100.0 * masses[0]
                    + stocks.all_mix_pwt / 100.0 * masses[2])
    additive_mass = (stocks.solvents_cswt / 100.0 * masses[1]
                     + stocks.all_mix_cswt / 100.0 * masses[2])
    return {
        "polymer_wt_percent": 100.0 * polymer_mass / total_mass,
        "additive_wt_percent": 100.0 * additive_mass / total_mass,
        "solvent_wt_percent": 100.0 * (total_mass - polymer_mass - additive_mass) / total_mass,
    }


def calculate_mix(recipe, stocks, round_to_uL=True, min_volume_tolerance_uL=1e-6):
    if isinstance(stocks, LegacyStockParameters):
        return _calculate_mix_legacy(recipe, stocks, round_to_uL, min_volume_tolerance_uL)
    return _calculate_mix_four_bottle(recipe, stocks, round_to_uL, min_volume_tolerance_uL)


def _calculate_mix_legacy(recipe, stocks, round_to_uL=True, min_volume_tolerance_uL=1e-6):
    if recipe.total_volume_uL <= 0:
        raise ValueError("Target total volume must be positive.")
    target_p = recipe.target_polymer_wt_percent / 100.0
    target_a = recipe.target_additive_wt_percent / 100.0
    stock_p = stocks.polymer_stock_wt_percent / 100.0
    additive_p = stocks.additive_stock_polymer_wt_percent / 100.0
    additive_a = stocks.additive_stock_additive_wt_percent / 100.0
    rho_p = stocks.polymer_stock_density
    rho_a = stocks.additive_stock_density
    rho_s = stocks.solvent_density
    if target_p < 0 or target_a < 0 or target_p + target_a >= 1:
        raise ValueError("Target wt% values must be non-negative and sum to less than 100.")
    if min(stock_p, additive_p, additive_a) < 0 or min(rho_p, rho_a, rho_s) <= 0:
        raise ValueError("Stock concentrations must be non-negative and densities must be positive.")
    if target_a > 0 and additive_a <= 0:
        raise ValueError("Target additive is nonzero, but additive stock contains no additive.")

    matrix = [
        [(stock_p - target_p) * rho_p, (additive_p - target_p) * rho_a, -target_p * rho_s],
        [-target_a * rho_p, (additive_a - target_a) * rho_a, -target_a * rho_s],
        [1.0, 1.0, 1.0],
    ]
    vp, va, vs = _solve_3x3(matrix, [0.0, 0.0, recipe.total_volume_uL])
    if min(vp, va, vs) < -min_volume_tolerance_uL:
        raise ValueError("Impossible formulation; target is outside the legacy stock feasible region.")
    vp, va, vs = max(vp, 0.0), max(va, 0.0), max(vs, 0.0)
    if round_to_uL:
        vp, va = round(vp), round(va)
        vs = round(recipe.total_volume_uL - vp - va)
        if vs < -min_volume_tolerance_uL:
            raise ValueError("Rounded volumes made solvent negative; use a larger total volume.")
        vs = max(vs, 0.0)

    masses = (vp * rho_p, va * rho_a, vs * rho_s)
    total_mass = sum(masses)
    polymer_mass = stock_p * masses[0] + additive_p * masses[1]
    additive_mass = additive_a * masses[1]
    return LegacyMixingResult(
        vp, va, vs, vp + va + vs,
        100.0 * polymer_mass / total_mass,
        100.0 * additive_mass / total_mass,
        100.0 * (total_mass - polymer_mass - additive_mass) / total_mass,
    )


def _calculate_mix_four_bottle(recipe, stocks, round_to_uL=True, min_volume_tolerance_uL=1e-6):
    if recipe.total_volume_uL <= 0:
        raise ValueError("Target total volume must be positive.")
    target_p = recipe.target_polymer_wt_percent / 100.0
    target_c = recipe.target_additive_wt_percent / 100.0
    if target_p < 0 or target_c < 0 or target_p + target_c >= 1:
        raise ValueError("Target wt% values must be non-negative and sum to less than 100.")

    stock_p, stock_c = stocks.polymer_stock_pwt / 100.0, stocks.solvents_cswt / 100.0
    all_p, all_c = stocks.all_mix_pwt / 100.0, stocks.all_mix_cswt / 100.0
    rho_p, rho_c = stocks.polymer_stock_density, stocks.cosolvent_stock_density
    rho_a, rho_s = stocks.all_mix_stock_density, stocks.solvent_density
    if min(rho_p, rho_c, rho_a, rho_s) <= 0:
        raise ValueError("All densities must be positive.")

    def solve_triangle(edge_p, edge_c, edge_density):
        matrix = [
            [(edge_p - target_p) * edge_density, (all_p - target_p) * rho_a, -target_p * rho_s],
            [(edge_c - target_c) * edge_density, (all_c - target_c) * rho_a, -target_c * rho_s],
            [1.0, 1.0, 1.0],
        ]
        return _solve_3x3(matrix, [0.0, 0.0, recipe.total_volume_uL])

    candidates = []
    for name, edge_p, edge_c, density in (
        ("polymer", stock_p, 0.0, rho_p), ("cosolvent", 0.0, stock_c, rho_c)):
        edge, allmix, solvent = solve_triangle(edge_p, edge_c, density)
        if min(edge, allmix, solvent) >= -min_volume_tolerance_uL:
            candidates.append((name, max(edge, 0.0), max(allmix, 0.0), max(solvent, 0.0)))
    if not candidates:
        raise ValueError("Impossible formulation; target is outside the four-stock feasible region.")

    name, edge, va, vs = candidates[0]
    vp, vc = (edge, 0.0) if name == "polymer" else (0.0, edge)
    if round_to_uL:
        vp, vc, va = round(vp), round(vc), round(va)
        vs = round(recipe.total_volume_uL - vp - vc - va)
        if vs < -min_volume_tolerance_uL:
            raise ValueError("Rounded volumes made solvent negative; use a larger total volume.")
        vs = max(vs, 0.0)
    final = check_final_composition(vp, vc, va, vs, stocks)
    return MixingResult(vp, vc, va, vs, vp + vc + va + vs,
                        final["polymer_wt_percent"], final["additive_wt_percent"],
                        final["solvent_wt_percent"])


def calculate_batch(recipe, stocks, round_to_uL=True):
    """Compatibility wrapper retained for the OT-2 protocol."""
    return calculate_mix(recipe, stocks, round_to_uL=round_to_uL)


def print_result(recipe, result):
    print("Target: {:.4g} wt% polymer, {:.4g} wt% additive, {:.2f} uL".format(
        recipe.target_polymer_wt_percent, recipe.target_additive_wt_percent, recipe.total_volume_uL))
    if isinstance(result, LegacyMixingResult):
        print("Volumes (uL): polymer={:.2f}, polymer-additive={:.2f}, solvent={:.2f}".format(
            result.normal_polymer_stock_uL, result.polymer_additive_stock_uL, result.solvent_uL))
    else:
        print("Volumes (uL): polymer={:.2f}, solvent-additive={:.2f}, all-mix={:.2f}, solvent={:.2f}".format(
            result.polymer_stock_uL, result.cosolvent_stock_uL, result.all_mix_stock_uL, result.solvent_uL))
