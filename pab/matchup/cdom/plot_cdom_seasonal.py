"""Seasonal pattern panel: Argo CDOM vs. BING Adg, small multiples by meteorological season.

Per C3/C4: qualitative/correlative only (no 1:1 line), and take the smaller N
as-is.

Usage
-----
    python pab/matchup/cdom/plot_cdom_seasonal.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from scipy import stats

from pab.matchup.cdom.data import (
    DEFAULT_DB,
    QUANTITY_CAVEAT,
    restrict_to_aoml,
    valid_cdom,
)
from pab.matchup.chl.data import load_chl_matchups

SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]
SEASON_COLORS = {
    "DJF": "#3182bd",
    "MAM": "#31a354",
    "JJA": "#e6550d",
    "SON": "#756bb1",
}


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("cdom_vs_adg_seasonal.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_cdom_seasonal(df, *, outfile=None, dpi: int = 200):
    """Small-multiples scatter, one panel per season, each with its own Spearman ρ."""
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2), sharex=True, sharey=True)
    for ax, season in zip(axes, SEASON_ORDER, strict=True):
        sub = df[df["season"] == season]
        if sub.empty:
            ax.set_title(f"{season} (n=0)")
            continue
        rho, _ = stats.spearmanr(sub["cdom"], sub["adg_bing"])
        ax.scatter(
            sub["cdom"],
            sub["adg_bing"],
            s=8,
            alpha=0.35,
            color=SEASON_COLORS[season],
            linewidths=0,
        )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(f"{season}  (n={len(sub)}, " + rf"$\rho$={rho:.2f})", fontsize=10)
        ax.set_xlabel("Argo CDOM [ppb QSDE]")
    axes[0].set_ylabel(r"BING $A_{dg}$ [m$^{-1}$]")
    fig.suptitle(
        f"Argo CDOM vs. PACE-fitted $A_{{dg}}$ by season — AOML, cdom < 6 ppb  (n = {len(df)} total)",
        y=1.04,
    )
    fig.text(0.5, -0.06, QUANTITY_CAVEAT, ha="center", fontsize=7.5, color="#555555")
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
    plot_cdom_seasonal(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
