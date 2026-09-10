"""Argo CDOM vs. BING fitted CDOM+detrital amplitude (Adg) — qualitative/correlative only.

Per C3: **no 1:1 line, no bias percentage.** Argo CDOM (ppb QSDE, a
fluorescence proxy) and BING's ``Adg`` (m^-1, a *combined* CDOM + detrital
absorption coefficient) are different quantities with no fixed conversion —
this is a rank-correlation/pattern comparison, not a retrieval-accuracy test.

Per the R1/R3 refinement pass, the population is restricted to ``cdom < 6``
ppb QSDE and AOML-processed floats only (replacing the prior unrestricted
figure).

Usage
-----
    python pab/matchup/cdom/plot_cdom_scatter.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from scipy import stats

from pab.matchup.cdom.data import (
    DEFAULT_DB,
    QUANTITY_CAVEAT,
    add_caveat_box,
    restrict_to_aoml,
    valid_cdom,
)
from pab.matchup.chl.data import load_chl_matchups


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("cdom_vs_adg_scatter.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_cdom_scatter(df, *, outfile=None, dpi: int = 200):
    """Log-log scatter of raw Argo ``cdom`` vs. fitted ``adg_bing``, Spearman ρ annotated."""
    rho, pval = stats.spearmanr(df["cdom"], df["adg_bing"])
    n = len(df)

    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.scatter(
        df["cdom"], df["adg_bing"], s=8, alpha=0.3, color="#238b45", linewidths=0
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Argo CDOM [ppb QSDE]")
    ax.set_ylabel(r"BING fitted CDOM+detrital amplitude $A_{dg}$ [m$^{-1}$]")
    ax.set_title(
        f"Argo CDOM vs. PACE-fitted $A_{{dg}}$ — AOML, cdom < 6 ppb  (n = {n})\n"
        rf"Spearman $\rho$ = {rho:.2f}  (p={pval:.1e})"
    )
    add_caveat_box(ax, text=QUANTITY_CAVEAT)
    fig.tight_layout()

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
    plot_cdom_scatter(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
