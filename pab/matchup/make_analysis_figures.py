"""
Generate the standard PACE–Argo bbp700 analysis figures from a PAB database.

Figures produced
----------------
bbp700_reldiff_histogram.png     – distribution of relative differences
bbp700_pace_vs_argo_scatter.png  – 1:1 scatter on log-log axes
bbp700_reldiff_vs_dtime.png      – rel-diff vs temporal separation
bbp700_reldiff_vs_dist.png       – rel-diff vs spatial separation
bbp700_reldiff_vs_mld.png        – rel-diff vs mixed-layer depth
bbp700_reldiff_seasonal.png      – seasonal cycle by hemisphere
bbp700_reldiff_by_basin.png      – basin comparison

Usage
-----
    python pab/matchup/make_analysis_figures.py
    python pab/matchup/make_analysis_figures.py --db /path/to/pab.db
    python pab/matchup/make_analysis_figures.py --db /path/to/pab.db --out-dir /path/to/figs
    python pab/matchup/make_analysis_figures.py --which histogram scatter
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from pab.config import DATA_DIR
from pab.db.store import Store
from pab.metrics.compare import gather_matchups

mpl.use("Agg")

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_DB = Path(DATA_DIR) / "pab.db"
DEFAULT_OUT = Path(DATA_DIR)

# Relative difference: (PACE − Argo) / PACE
# Normalized by PACE so δ ∈ (−∞, 1); positive = PACE > Argo.
REL_DIFF_CLIP = -1.5   # lower clip; upper bound is +1 by construction


# ── helpers ───────────────────────────────────────────────────────────────────

def _basin(lat: float, lon: float) -> str:
    if lat <= -35:
        return "Southern"
    if -70 <= lon < 20:
        return "Atlantic"
    if 20 <= lon < 100:
        return "Indian"
    return "Pacific"


def _load(db: Path) -> pd.DataFrame:
    """Return a merged DataFrame with matchup data + geometry + MLD."""
    with Store.open(db, create=False) as store:
        df = gather_matchups(store)

    if df.empty:
        raise RuntimeError(f"No matchups found in {db}")

    df["time"] = pd.to_datetime(df["time"])
    df["rel_diff"] = (df["bbp_bing"] - df["bbp_argo"]) / df["bbp_bing"]

    # Join geometry (distance_km, dtime_hours) and MLD from the raw DB
    con = sqlite3.connect(db)
    geo = pd.read_sql(
        "SELECT matchup_id, distance_km, dtime_hours FROM matchups", con
    )
    mld_df = pd.read_sql(
        """SELECT p.profile_id, p.wmo, p.cycle, ms.mld
           FROM profiles p
           JOIN mld_summary ms ON ms.profile_id = p.profile_id""",
        con,
    )
    con.close()

    df = df.merge(geo, on="matchup_id", how="left")
    df = df.merge(
        mld_df[["wmo", "cycle", "mld"]], on=["wmo", "cycle"], how="left"
    )

    # Filter
    valid = (
        df["bbp_argo"].notna()
        & df["bbp_bing"].notna()
        & (df["bbp_argo"] > 0)
        & (df["bbp_bing"] > 0)
        & (df["rel_diff"] >= REL_DIFF_CLIP)
    )
    return df[valid].copy()


# ── figure functions ──────────────────────────────────────────────────────────

def histogram(df: pd.DataFrame, out: Path) -> mpl.figure.Figure:
    """Distribution of relative differences."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bins = np.arange(-1.5, 1.05, 0.05)
    ax.hist(
        df["rel_diff"],
        bins=bins,
        color="#5b8db8",
        edgecolor="white",
        lw=0.3,
    )
    med = df["rel_diff"].median()
    ax.axvline(med, color="#d6604d", lw=1.5, ls="--", label=f"Median = {med:+.3f}")
    ax.axvline(0, color="k", lw=0.8, ls=":")
    ax.set_xlabel(
        r"Relative $\Delta b_{bp}$ = (PACE $-$ Argo) / PACE", fontweight="bold"
    )
    ax.set_ylabel("Count")
    ax.set_title(r"Distribution of PACE–Argo relative $b_{bp}$")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig


def scatter_1to1(df: pd.DataFrame, out: Path) -> mpl.figure.Figure:
    """Log-log 1:1 scatter of PACE vs Argo bbp700."""
    valid = df[["bbp_argo", "bbp_bing"]].dropna()
    n = len(valid)
    log_a = np.log10(valid["bbp_argo"])
    log_b = np.log10(valid["bbp_bing"])
    rho, _ = stats.spearmanr(valid["bbp_argo"], valid["bbp_bing"])
    bias = float(np.mean(log_b - log_a))
    rms = float(np.sqrt(np.mean((log_b - log_a) ** 2)))
    med_ratio = float(np.median(valid["bbp_bing"] / valid["bbp_argo"]))

    lo = 10 ** (min(log_a.min(), log_b.min()) - 0.3)
    hi = 10 ** (max(log_a.max(), log_b.max()) + 0.3)

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.scatter(valid["bbp_argo"], valid["bbp_bing"], s=4, alpha=0.3,
               color="#5b8db8", linewidths=0)
    ax.plot([lo, hi], [lo, hi], "k-", lw=1.2, label="1:1")
    ax.plot([lo, hi], [lo * med_ratio, hi * med_ratio], "r--", lw=1.2,
            label=f"Median ratio = {med_ratio:.2f}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel(r"Argo $b_{bp,700}$ [m$^{-1}$]")
    ax.set_ylabel(r"PACE $b_{bp,700}$ [m$^{-1}$]")
    ax.set_title(
        r"Argo $b_{bp,700}$ vs. PACE $b_{bp,700}$"
        f"\nn={n}  ρ={rho:.2f}  bias={bias:+.2f}  RMS={rms:.2f} (log10)"
    )
    ax.legend(frameon=False)
    ax.grid(True, which="major", lw=0.4, alpha=0.5, color="#aaa")
    ax.grid(True, which="minor", lw=0.25, alpha=0.3, color="#ccc")
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig


def _scatter_vs(df: pd.DataFrame, xcol: str, xlabel: str, out: Path,
                xscale: str = "linear", bins: int = 5) -> mpl.figure.Figure:
    """Generic rel_diff vs. x scatter with quintile medians."""
    sub = df.dropna(subset=[xcol, "rel_diff"]).copy()
    rho, pval = stats.spearmanr(sub[xcol], sub["rel_diff"])
    p_str = "p < 0.001" if pval < 0.001 else f"p = {pval:.3f}"

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(sub[xcol], sub["rel_diff"], s=4, alpha=0.2,
               color="#5b8db8", linewidths=0)
    ax.axhline(0, color="k", lw=0.8, ls="--")

    # Quintile medians
    sub["_q"] = pd.qcut(sub[xcol], bins, labels=False, duplicates="drop")
    qmed = sub.groupby("_q").agg(xm=(xcol, "median"), ym=("rel_diff", "median"))
    ax.plot(qmed["xm"], qmed["ym"], "r-o", lw=1.5, ms=5, zorder=3,
            label="Quintile medians")

    if xscale == "log":
        ax.set_xscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(r"Relative $\Delta b_{bp}$")
    ax.set_title(f"{xlabel} vs. relative $\\Delta b_{{bp}}$\nSpearman ρ = {rho:.2f}, {p_str}")
    ax.set_ylim(-1.05, 1.05)
    ax.grid(True, lw=0.4, alpha=0.4, color="#ccc")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig


def reldiff_vs_dtime(df: pd.DataFrame, out: Path) -> mpl.figure.Figure:
    return _scatter_vs(
        df, "dtime_hours",
        r"$\Delta t$ between PACE overpass and Argo profile (hours)", out
    )


def reldiff_vs_dist(df: pd.DataFrame, out: Path) -> mpl.figure.Figure:
    return _scatter_vs(
        df, "distance_km",
        "Matchup distance (km)", out
    )


def reldiff_vs_mld(df: pd.DataFrame, out: Path) -> mpl.figure.Figure:
    return _scatter_vs(
        df, "mld",
        "Mixed-layer depth (m)", out, xscale="log"
    )


def seasonal(df: pd.DataFrame, out: Path) -> mpl.figure.Figure:
    """Seasonal cycle of rel_diff by hemisphere (SH months shifted +6)."""
    df = df.copy()
    df["month"] = df["time"].dt.month
    df["hemi"] = df["latitude"].apply(lambda x: "NH" if x >= 0 else "SH")
    df["local_month"] = df.apply(
        lambda r: r["month"] if r["hemi"] == "NH"
        else ((r["month"] - 1 + 6) % 12) + 1,
        axis=1,
    )

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for hemi, color, label in [("NH", "#3a7ebf", "Northern Hemisphere"),
                                ("SH", "#e07b39", "Southern Hemisphere (shifted +6 mo)")]:
        sub = df[df["hemi"] == hemi]
        med = sub.groupby("local_month")["rel_diff"].median()
        ax.plot(med.index, med.values, "o-", color=color, lw=1.5, ms=5, label=label)
        ax.fill_between(
            med.index,
            sub.groupby("local_month")["rel_diff"].quantile(0.25),
            sub.groupby("local_month")["rel_diff"].quantile(0.75),
            color=color, alpha=0.15,
        )
    ax.axhline(df["rel_diff"].median(), color="gray", lw=0.8, ls="--",
               label=f"Overall median = {df['rel_diff'].median():+.3f}")
    ax.axhline(0, color="k", lw=0.6, ls=":")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], fontsize=8)
    ax.set_xlabel("Local month")
    ax.set_ylabel(r"Relative $\Delta b_{bp}$")
    ax.set_title(
        r"Seasonal cycle of relative $\Delta b_{bp}$ by hemisphere"
        "\n(shaded band = interquartile range)"
    )
    ax.set_ylim(-0.4, 1.0)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig


def by_basin(df: pd.DataFrame, out: Path) -> mpl.figure.Figure:
    """Box/violin of rel_diff by ocean basin."""
    df = df.copy()
    df["basin"] = [_basin(r.latitude, r.longitude)
                   for r in df[["latitude", "longitude"]].itertuples()]
    order = ["Atlantic", "Pacific", "Indian", "Southern"]
    groups = [df[df["basin"] == b]["rel_diff"].dropna().values for b in order]
    labels = [f"{b}\n(n={len(g):,})" for b, g in zip(order, groups, strict=True)]

    fig, ax = plt.subplots(figsize=(8, 5))
    parts = ax.violinplot(groups, positions=range(len(order)),
                          showmedians=True, showextrema=False)
    for pc in parts["bodies"]:
        pc.set_facecolor("#5b8db8")
        pc.set_alpha(0.6)
    parts["cmedians"].set_color("#d6604d")
    parts["cmedians"].set_lw(2)
    ax.axhline(0, color="k", lw=0.8, ls="--")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel(r"Relative $\Delta b_{bp}$")
    ax.set_title(r"Relative $b_{bp}$ bias by ocean basin")
    ax.set_ylim(-1.05, 1.05)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig


# ── entry point ───────────────────────────────────────────────────────────────

FIGURES = {
    "histogram": (histogram,      "bbp700_reldiff_histogram.png"),
    "scatter":   (scatter_1to1,   "bbp700_pace_vs_argo_scatter.png"),
    "dtime":     (reldiff_vs_dtime, "bbp700_reldiff_vs_dtime.png"),
    "dist":      (reldiff_vs_dist,  "bbp700_reldiff_vs_dist.png"),
    "mld":       (reldiff_vs_mld,   "bbp700_reldiff_vs_mld.png"),
    "seasonal":  (seasonal,         "bbp700_reldiff_seasonal.png"),
    "basin":     (by_basin,         "bbp700_reldiff_by_basin.png"),
}


def generate_all(db: Path, out_dir: Path, which: list[str] | None = None) -> None:
    print(f"Loading matchups from {db} …")
    df = _load(db)
    n = len(df)
    print(f"  {n:,} valid matchups, {df['wmo'].nunique()} floats")
    print(f"  Median δ = {df['rel_diff'].median():+.3f}, "
          f"{(df['rel_diff'] > 0).sum() / n * 100:.1f}% positive")

    out_dir.mkdir(parents=True, exist_ok=True)

    keys = which if which else list(FIGURES)
    for key in keys:
        if key not in FIGURES:
            print(f"  Unknown figure '{key}', skipping")
            continue
        fn, fname = FIGURES[key]
        out_path = out_dir / fname
        fn(df, out_path)
        print(f"  ✓ {fname}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate PACE–Argo bbp700 analysis figures."
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to PAB SQLite database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT,
        help=f"Directory for output PNGs (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--which", nargs="+", choices=list(FIGURES),
        help="Subset of figures to generate (default: all)",
    )
    args = parser.parse_args()
    generate_all(args.db, args.out_dir, args.which)
