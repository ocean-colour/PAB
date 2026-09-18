"""Chl-a relative-difference stratification panels: Δt, distance, MLD, season, basin.

Mirrors ``bbp700_reldiff_vs_dtime.png``/``_vs_dist.png``
(``pace_argo_bbp700_bias_analysis.md``) and ``bbp700_reldiff_vs_mld.png``/
``_seasonal.png``/``_by_basin.png`` (``pace_argo_analysis_figures.md``), applied
to Chl-a rather than bbp700, at the full N ≈ 14.6k matchup set.

Usage
-----
    python pab/matchup/chl/plot_chl_stratification.py --outdir .
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups, valid_chl

MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
BASIN_ORDER = ["Atlantic", "Pacific", "Indian", "Southern"]
BASIN_COLORS = {
    "Atlantic": "#1f77b4",
    "Pacific": "#2ca02c",
    "Indian": "#ff7f0e",
    "Southern": "#9467bd",
}


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--outdir", type=Path, default=Path("."))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def _octile_binned(x, y, n_bins: int = 8):
    """Equal-count bin medians of ``y`` over ``x`` (octiles, matching bbp700's octile plots)."""
    bins = np.unique(np.percentile(x, np.linspace(0, 100, n_bins + 1)))
    cats = pd.cut(x, bins=bins, include_lowest=True)
    med = pd.Series(y).groupby(cats, observed=True).median()
    mid = [(iv.left + iv.right) / 2 for iv in med.index]
    return mid, med.values


def plot_vs_geometry(df, col: str, xlabel: str, *, outfile=None, dpi: int = 200):
    """Rel-diff vs. a matchup-geometry column (``dtime_hours`` or ``distance_km``)."""
    sub = df[df[col].notna()].copy()
    x = sub[col].to_numpy(dtype=float)
    y = sub["rel_diff"].to_numpy(dtype=float)
    overall_med = float(np.median(y))

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    sc = ax.scatter(
        x,
        y,
        c=np.clip(y, -1, 1),
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        s=10,
        alpha=0.35,
        linewidths=0,
    )
    ax.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
    ax.axhline(
        overall_med,
        color="#7f0000",
        lw=1.5,
        label=f"overall median = {overall_med:+.2f}",
    )
    mid, bmed = _octile_binned(x, y)
    ax.plot(mid, bmed, "ko-", ms=6, lw=1.5, label="octile medians", zorder=5)
    fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02, label="Relative difference")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(r"$(Chl^{\rm PACE} - Chl^{\rm Argo})\,/\,Chl^{\rm PACE}$")
    ax.set_title(f"Chl-a relative difference vs. {xlabel}  (n = {len(sub)})")
    ax.legend(fontsize=9)
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_vs_mld(df, *, outfile=None, dpi: int = 200):
    sub = df[df["mld"].notna() & (df["mld"] > 0)].copy()
    return plot_vs_geometry(
        sub, "mld", "Mixed layer depth (m)", outfile=outfile, dpi=dpi
    )


def plot_seasonal(df, *, outfile=None, dpi: int = 200):
    """Rel-diff by month, jittered scatter + monthly medians (mirrors the bbp700 figure)."""
    sub = df[df["season"].notna()].copy()
    sub["month"] = pd.to_datetime(sub["time"], utc=True, errors="coerce").dt.month
    sub = sub[sub["month"].notna()]
    overall_med = float(sub["rel_diff"].median())

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
    ax.axhline(
        overall_med,
        color="gray",
        lw=1,
        ls=":",
        label=f"overall median = {overall_med:+.2f}",
    )
    for m in range(1, 13):
        vals = sub.loc[sub["month"] == m, "rel_diff"]
        if vals.empty:
            continue
        jit = np.random.default_rng(m).uniform(-0.2, 0.2, len(vals))
        ax.scatter(m + jit, vals, s=6, alpha=0.2, color="#2ca25f", linewidths=0)
    meds = sub.groupby("month")["rel_diff"].median()
    ax.plot(
        meds.index,
        meds.values,
        "o-",
        color="#00441b",
        ms=7,
        lw=2,
        label="monthly median",
        zorder=5,
    )
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTHS, fontsize=9)
    ax.set_xlabel("Month (profile observation)")
    ax.set_ylabel(r"$(Chl^{\rm PACE} - Chl^{\rm Argo})\,/\,Chl^{\rm PACE}$")
    ax.set_title(f"Seasonal cycle of Chl-a relative difference  (n = {len(sub)})")
    ax.legend(fontsize=9)
    ax.set_ylim(-1.6, 1.6)
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_by_basin(df, *, outfile=None, dpi: int = 200):
    """Rel-diff by ocean basin, jittered scatter + median bars (mirrors the bbp700 figure)."""
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
    for i, bas in enumerate(BASIN_ORDER):
        sub = df.loc[df["basin"] == bas, "rel_diff"]
        if sub.empty:
            continue
        jit = np.random.default_rng(i).uniform(-0.15, 0.15, len(sub))
        ax.scatter(
            i + jit, sub.values, s=8, alpha=0.3, color=BASIN_COLORS[bas], linewidths=0
        )
        ax.plot(
            [i - 0.25, i + 0.25],
            [sub.median(), sub.median()],
            color=BASIN_COLORS[bas],
            lw=2.5,
            solid_capstyle="round",
            label=f"{bas} (n={len(sub)}, med={sub.median():+.2f})",
        )
    ax.set_xticks(range(len(BASIN_ORDER)))
    ax.set_xticklabels(BASIN_ORDER, fontsize=11)
    ax.set_ylabel(r"$(Chl^{\rm PACE} - Chl^{\rm Argo})\,/\,Chl^{\rm PACE}$")
    ax.set_title(f"Chl-a relative difference by ocean basin  (n = {len(df)})")
    ax.legend(fontsize=9, loc="lower right")
    ax.set_ylim(-1.6, 1.6)
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
    print(f"Loaded {len(df)} valid Chl-a matchups")
    args.outdir.mkdir(parents=True, exist_ok=True)

    plot_vs_geometry(
        df,
        "dtime_hours",
        "Time separation Δt (hours)",
        outfile=args.outdir / "chl_reldiff_vs_dtime.png",
        dpi=args.dpi,
    )
    plot_vs_geometry(
        df,
        "distance_km",
        "Spatial separation (km)",
        outfile=args.outdir / "chl_reldiff_vs_dist.png",
        dpi=args.dpi,
    )
    plot_vs_mld(df, outfile=args.outdir / "chl_reldiff_vs_mld.png", dpi=args.dpi)
    plot_seasonal(df, outfile=args.outdir / "chl_reldiff_seasonal.png", dpi=args.dpi)
    plot_by_basin(df, outfile=args.outdir / "chl_reldiff_by_basin.png", dpi=args.dpi)


if __name__ == "__main__":
    main()
