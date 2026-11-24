"""Apply the reviewed physical-position decisions to a notebook's aggregate selection.

The register contains identities and fit-row references. Measurements are read
from the referenced reps.csv files. To refresh the register after a new review:

    uv run python EVALUATE/campaign_screening.py <reviewed-study-directory>
"""
from argparse import ArgumentParser
from pathlib import Path

import numpy as np
import pandas as pd

from campaign_trends import DEFAULT_PROPERTIES, available_properties

REGISTER = Path("EVALUATE/campaign_position_review.csv")
KEY = ["campaign", "condition"]
FILM = [*KEY, "record_id", "screening_phase", "position_decision", "position_reason"]
SITE = ["physical_site_id", "position", "fit_csv", "fit_name", "trial",
        "reviewed_modulus_bar", "reviewed_pore_fraction"]
SEARCH_PHASES = ("Exploration", "Dual objective", "Dual + explore")
OBJECTIVES = ["Elastic Modulus", "Pore Fraction"]
COMPRESSION_PROPERTIES = (*DEFAULT_PROPERTIES, "Slope Plateau", "Slope Densification",
                          "Strain at 80 bar", "Strain at 150 bar", "Strain at 500 bar",
                          "Pore Fraction Unsubtracted")


def build_position_register(study):
    """Project signed film and punch identities for the reviewed discovery campaigns."""
    study = Path(study)
    films = pd.read_csv(study / "screening/cohorts/films.csv",
                        usecols=["source_folder", "in_acquisition", *KEY, "phase"])
    decisions = pd.read_csv(study / "review/decisions.csv", usecols=[
        "source_folder", *KEY, "record_id", "decision", "reason_code", "n_used"])
    films = films.loc[films.in_acquisition].merge(decisions, on=["source_folder", *KEY],
                                                   how="left", validate="one_to_one")
    films = films.rename(columns={"phase": "screening_phase", "decision": "position_decision",
                                  "reason_code": "position_reason"})
    punches = pd.read_csv(study / "review/punches.csv", usecols=[
        "record_id", "physical_site_id", "position", "used_in_paper",
        "pairing_verified", "E_primary", "phi_primary", "E_bar", "phi",
        "archived_fit_lookup_name", "fit_csv", "trial"])
    # This flag belongs to the physical review, before the notebook's aggregate gate.
    punches = punches.loc[punches.used_in_paper & punches.record_id.isin(films.record_id)].copy()
    if not punches[["pairing_verified", "E_primary", "phi_primary"]].all().all():
        raise ValueError("A signed position lacks pairing or a passing fit for both objectives")
    punches = punches.rename(columns={"archived_fit_lookup_name": "fit_name", "E_bar": "reviewed_modulus_bar",
                                      "phi": "reviewed_pore_fraction"})
    counts = films.record_id.map(punches.groupby("record_id").size()).fillna(0)
    if not counts.eq(films.n_used).all():
        raise ValueError("The signed position counts disagree with the film decisions")
    register = films[FILM].merge(punches[["record_id", *SITE]], on="record_id",
                                 how="left", validate="one_to_many")
    register["position"] = register.position.astype("Int64")
    validate_register(register)
    return register.sort_values(["record_id", "position"]).reset_index(drop=True)


def validate_register(register):
    films = register[FILM].drop_duplicates()
    if (films.isna().any().any() or films.duplicated(KEY).any() or not films.record_id.is_unique
            or not films.position_decision.isin(["KEEP", "DISCARD"]).all()):
        raise ValueError("Missing, conflicting or duplicated film decisions in the position register")
    kept = register.position_decision.eq("KEEP")
    sites = register.loc[kept]
    if (sites[SITE].isna().any().any() or register.loc[~kept, SITE].notna().any().any()
            or register.loc[~kept, "record_id"].duplicated().any()
            or not sites.physical_site_id.is_unique or sites.duplicated(["record_id", "position"]).any()
            or sites.duplicated(["fit_csv", "fit_name", "trial"]).any()
            or (sites.groupby("record_id").size() < 2).any()):
        raise ValueError("Each kept film requires at least two distinct, traceable paired positions")


def apply_position_screen(aggregate, root):
    """Return screened film measurements and the disposition of every aggregate-gate survivor."""
    root = Path(root)
    register = pd.read_csv(root / REGISTER)
    validate_register(register)
    films = register[FILM].drop_duplicates()
    checked = aggregate.merge(films, on=KEY, how="left", validate="one_to_one")
    modulus = pd.to_numeric(checked["Elastic Modulus Mean"], errors="coerce")
    pore = pd.to_numeric(checked["Pore Fraction Mean"], errors="coerce")
    pair = np.isfinite(modulus) & modulus.gt(0) & pore.between(0, 1)
    checked["screening_outcome"] = np.select(
        [checked.record_id.isna(), ~pair, checked.position_decision.ne("KEEP")],
        ["No reviewed film", "Missing or invalid aggregate objective pair", "Failed position review"],
        default="Retained")
    log = checked[[*FILM, "screening_outcome"]].copy()
    selected = checked.loc[checked.screening_outcome.eq("Retained")].copy()
    if selected.empty:
        raise ValueError("No films pass both screens. Aggregate-gate outcomes: "
                         + str(log.screening_outcome.value_counts().to_dict()))
    refs = register.loc[register.record_id.isin(selected.record_id), ["record_id", *SITE]]
    properties = [prop for prop in available_properties(aggregate) if prop in COMPRESSION_PROPERTIES]
    positions = []
    for relative, group in refs.groupby("fit_csv", sort=False):
        fits = pd.read_csv(root / relative, usecols=lambda col: col in ["name", "Trial", *properties])
        fits = fits.rename(columns={"name": "fit_name", "Trial": "trial"})
        measured = group.merge(fits, on=["fit_name", "trial"], how="left",
                               validate="one_to_one", indicator=True)
        if not measured["_merge"].eq("both").all():
            raise ValueError(f"A reviewed position has no matching measured fit in {relative}")
        positions.append(measured)
    positions = pd.concat(positions, ignore_index=True)
    values = positions.reindex(columns=properties).apply(pd.to_numeric, errors="coerce")
    values = values.where(np.isfinite(values))
    if (values[OBJECTIVES].isna().any().any() or not values["Elastic Modulus"].gt(0).all()
            or not values["Pore Fraction"].between(0, 1).all()):
        raise ValueError("The referenced fit no longer has the two reviewed physical endpoints")
    if not np.allclose(values[OBJECTIVES], positions[["reviewed_modulus_bar", "reviewed_pore_fraction"]],
                       rtol=1e-11, atol=1e-13):
        raise ValueError("A measured fit has changed since its position was reviewed")
    groups = values.groupby(positions.record_id)
    # Ambient measurements and aggregate QC diagnostics are casting-level provenance.
    # Only measured compression properties are rebuilt on the paired positions.
    metrics = pd.concat([groups.mean().add_suffix(" Mean"), groups.std(ddof=1).add_suffix(" SD"),
                         groups.count().add_suffix(" N")], axis=1)
    metrics["screened_position_count"] = groups.size()
    selected = selected.drop(columns=[col for col in metrics if col in selected]).join(
        metrics, on="record_id", validate="one_to_one")
    # These generated reports quote older aggregate measurements. The original text
    # stays in source_csv and the warm-start exporter builds fresh reports for this cohort.
    selected = selected.drop(columns=["formatted_parameters_withProp", "initial_report", "final_report"],
                             errors="ignore")
    return selected.reset_index(drop=True), log


def search_trajectory(films):
    """Number only screened search films in chronological order."""
    search = films.loc[films.screening_phase.isin(SEARCH_PHASES)].sort_values(
        ["sample_time", *KEY]).reset_index(drop=True)
    search["iteration"] = search.index + 1
    return search


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    args = parser.parse_args()
    build_position_register(args.study).to_csv(Path(__file__).resolve().parents[1] / REGISTER, index=False)
