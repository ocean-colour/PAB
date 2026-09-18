"""Histogram of Chl-a relative difference: (PACE - Argo) / PACE.

Mirrors the bbp700 headline-bias histogram (``bbp700_reldiff_histogram.png``).

Usage
-----
    python pab/matchup/chl/plot_chl_histogram.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups, valid_chl


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("chl_reldiff_histogram.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_chl_histogram(df, *, outfile=None, dpi: int = 200):
    """Histogram of ``rel_diff`` with % positive and median annotated."""
    rd = df["rel_diff"].to_numpy(dtype=float)
    n = len(rd)
    n_pos = int((rd > 0).sum())
    med = float(np.median(rd))

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.hist(
        rd,
        bins=np.linspace(-1.5, 1.5, 32),
        color="#2ca25f",
        alpha=0.85,
        edgecolor="white",
        linewidth=0.4,
    )
    ax.axvline(0, color="#444", lw=1.0, ls="--", label="Zero")
    ax.axvline(med, color="#00441b", lw=1.8, ls="-", label=f"Median = {med:+.2f}")
    ax.set_xlabel("Relative difference  (PACE − Argo) / PACE")
    ax.set_ylabel("Number of matchups")
    ax.set_title(
        f"PACE Chl-a exceeds Argo in {n_pos} of {n} matchups ({100 * n_pos / n:.0f}%)"
    )
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
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
    df = valid_chl(df, clip=1.5)
    print(f"Loaded {len(df)} valid Chl-a matchups (|rel_diff| <= 1.5)")
    plot_chl_histogram(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
