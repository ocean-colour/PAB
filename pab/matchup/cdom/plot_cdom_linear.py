"""Argo CDOM vs. BING Adg on a LINEAR scale, with an illustrative OLS fit line.

Per R4/R7 (chl_cdom_matchups.md): unlike every other CDOM figure in this
project, this one carries a fitted trend line — a deliberate, one-off
exception to C3 ("no 1:1 line, no bias/conversion claim"), made explicitly at
JXP's request. The fit is plain OLS with an intercept (R7), and is captioned
as an **illustrative/exploratory trend only** — NOT a validated or
recommended ppb-to-m^-1 conversion factor. Every other CDOM comparison in
this project stays free of any fitted line; this figure is the sole,
consciously-flagged exception.

Population: AOML floats only, cdom < 6 ppb QSDE (per R1/R3).

Usage
-----
    python pab/matchup/cdom/plot_cdom_linear.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from pab.matchup.cdom.data import (
    DEFAULT_DB,
    restrict_to_aoml,
    valid_cdom,
)
from pab.matchup.chl.data import load_chl_matchups

#: Per R7: this is the ONE figure in the CDOM analysis with a fitted line —
#: stated plainly so it is never mistaken for a recommended correction.
FIT_LINE_CAVEAT = (
    "Illustrative OLS trend only — NOT a validated or recommended\n"
    "ppb-to-m$^{-1}$ conversion. A deliberate, one-off exception to this\n"
    "project's no-1:1/no-conversion rule for CDOM (see R4/R7)."
)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("cdom_vs_adg_linear.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_cdom_linear(df, *, outfile=None, dpi: int = 200):
    """Linear-scale scatter of Argo ``cdom`` vs. fitted ``adg_bing``, with an OLS fit line."""
    x = df["cdom"].to_numpy(dtype=float)
    y = df["adg_bing"].to_numpy(dtype=float)
    n = len(df)
    rho, pval = stats.spearmanr(x, y)
    slope, intercept = np.polyfit(x, y, 1)
    r2 = np.corrcoef(x, y)[0, 1] ** 2

    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.scatter(x, y, s=8, alpha=0.3, color="#238b45", linewidths=0)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(
        xs,
        slope * xs + intercept,
        "k--",
        lw=1.5,
        label=f"OLS: $A_{{dg}}$ = {slope:.4f}×CDOM + {intercept:.4f} ($R^2$={r2:.2f})",
    )
    ax.set_xlabel("Argo CDOM [ppb QSDE]")
    ax.set_ylabel(r"BING fitted CDOM+detrital amplitude $A_{dg}$ [m$^{-1}$]")
    ax.set_title(
        f"Argo CDOM vs. PACE-fitted $A_{{dg}}$ — linear scale, AOML, cdom < 6 ppb  (n = {n})\n"
        rf"Spearman $\rho$ = {rho:.2f}  (p={pval:.1e})"
    )
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.text(0.5, -0.04, FIT_LINE_CAVEAT, ha="center", fontsize=7.5, color="#555555")

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def main(argv=None):
    args = _parse_args(argv)
    df = load_chl_matchups(args.db)
    df = restrict_to_aoml(valid_cdom(df))
    print(f"Loaded {len(df)} valid CDOM/Adg matchups (AOML, cdom < 6)")
    plot_cdom_linear(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
