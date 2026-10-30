"""Deterministic evidence figures from promoted campaign rows, without LLM calls."""
import csv
import math
from pathlib import Path


def build_figures(llm_csv, output_dir):
    """Plot promoted rows once; specimens and pre/post-discard rows are not pooled."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with Path(llm_csv).open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    fields = ["name", "Elastic Modulus Mean", "Elastic Modulus SD", "Changepoint Mean"]
    table = output_dir / "trajectory.csv"
    with table.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)
    from matplotlib.figure import Figure
    fig = Figure(figsize=(9, 4), layout="constrained")
    trajectory, tradeoff = fig.subplots(1, 2)
    points = []
    for i, row in enumerate(rows):
        try:
            modulus = float(row.get("Elastic Modulus Mean", ""))
        except (ValueError, TypeError):
            continue
        if not math.isfinite(modulus):
            continue
        trajectory.scatter(i + 1, modulus, color="tab:blue")
        try:
            pore = float(row.get("Changepoint Mean", ""))
        except (ValueError, TypeError):
            continue
        if math.isfinite(pore):
            points.append((pore, modulus))
    if points:
        tradeoff.scatter(*zip(*points))
    trajectory.set(xlabel="Promoted row order (not elapsed time)", ylabel="Elastic modulus (bar)")
    tradeoff.set(xlabel="Compression changepoint estimate (dimensionless)", ylabel="Elastic modulus (bar)")
    fig.suptitle("Observed values; no independent-synthesis uncertainty inferred")
    path = output_dir / "trajectory.png"
    fig.savefig(path, dpi=140)
    return [table, path]
