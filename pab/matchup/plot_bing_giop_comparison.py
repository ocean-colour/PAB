"""
Figure 16: Three-panel BING vs. GIOP comparison against BGC-Argo.

Panels:
  (a) BING bbp700 vs Argo — 1:1 scatter (log-log)
  (b) GIOP bbp700 vs Argo — 1:1 scatter (log-log)
  (c) Overlaid histogram of δ = (PACE − Argo)/PACE for both algorithms

GIOP bbp700 is extrapolated from fit_results (NASA_GIOP algorithm):
    bbp700 = bbp442 × (442/700)^η

Usage:
    python plot_bing_giop_comparison.py
    python plot_bing_giop_comparison.py --db /path/to/pab_full.db --out /path/to/out.png
"""
import argparse
import sqlite3
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from pab.config import DATA_DIR

DEFAULT_DB = Path(DATA_DIR) / "pab_full.db"
DEFAULT_PARQUET = Path(DATA_DIR) / "matchup_summary.parquet"
DEFAULT_OUT = Path(DATA_DIR) / "fig16_bing_giop_comparison.png"


def load_data(db=None, parquet=None):
    db_path = db or DEFAULT_DB
    par_path = parquet or DEFAULT_PARQUET

    # Pull GIOP bbp442 and spectral slope from fit_results
    con = sqlite3.connect(db_path)
    giop = pd.read_sql(
        """SELECT f.matchup_id,
                  MAX(CASE WHEN fr.quantity='NASA_GIOP_bbp_442' THEN fr.median END) AS giop_bbp442,
                  MAX(CASE WHEN fr.quantity='NASA_GIOP_bbp_s'   THEN fr.median END) AS giop_bbp_s
           FROM fits f
           JOIN fit_results fr ON fr.fit_id = f.fit_id
           WHERE f.algorithm = 'NASA_GIOP'
           GROUP BY f.matchup_id""",
        con,
    )
    con.close()

    par = pd.read_parquet(par_path)
    par = par.dropna(subset=["bbp_argo", "bbp_bing"])
    par = par[(par["bbp_argo"] > 0) & (par["bbp_bing"] > 0)].copy()

    df = par.merge(giop, on="matchup_id", how="inner")
    df = df.dropna(subset=["giop_bbp442", "giop_bbp_s"])
    df = df[(df["giop_bbp442"] > 0)].copy()

    # Extrapolate GIOP bbp to 700 nm
    df["bbp_giop700"] = df["giop_bbp442"] * (442 / 700) ** df["giop_bbp_s"]
    df = df[df["bbp_giop700"] > 0]

    # Relative biases
    df["delta_bing"] = (df["bbp_bing"] - df["bbp_argo"]) / df["bbp_bing"]
    df["delta_giop"] = (df["bbp_giop700"] - df["bbp_argo"]) / df["bbp_giop700"]

    return df


def make_figure(df, out=None):
    n = len(df)
    lo, hi = 10 ** -5, 10 ** -1

    med_b = df["delta_bing"].median()
    med_g = df["delta_giop"].median()
    pct_b = (df["delta_bing"] > 0).mean() * 100
    pct_g = (df["delta_giop"] > 0).mean() * 100

    rho_b, _ = stats.spearmanr(np.log10(df["bbp_argo"]), np.log10(df["bbp_bing"]))
    rho_g, _ = stats.spearmanr(np.log10(df["bbp_argo"]), np.log10(df["bbp_giop700"]))
    bias_b = np.mean(np.log10(df["bbp_bing"]) - np.log10(df["bbp_argo"]))
    bias_g = np.mean(np.log10(df["bbp_giop700"]) - np.log10(df["bbp_argo"]))
    rms_b = np.sqrt(np.mean((np.log10(df["bbp_bing"]) - np.log10(df["bbp_argo"])) ** 2))
    rms_g = np.sqrt(np.mean((np.log10(df["bbp_giop700"]) - np.log10(df["bbp_argo"])) ** 2))
    med_ratio_b = (df["bbp_bing"] / df["bbp_argo"]).median()
    med_ratio_g = (df["bbp_giop700"] / df["bbp_argo"]).median()

    RC = {
        "font.size": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "figure.dpi": 180, "axes.linewidth": 0.8,
    }

    with mpl.rc_context(RC):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.8))

        # (a) BING vs Argo
        ax = axes[0]
        ax.scatter(df["bbp_argo"], df["bbp_bing"], s=1.5, alpha=0.1,
                   color="#2166ac", linewidths=0, rasterized=True)
        ax.plot([lo, hi], [lo, hi], "k-", lw=1.2, label="1:1")
        ax.plot([lo, hi], [lo * med_ratio_b, hi * med_ratio_b], "b--", lw=1.2,
                label=f"Median ratio = {med_ratio_b:.2f}")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.set_xlabel(r"Argo $b_{bp,700}$ [m$^{-1}$]")
        ax.set_ylabel(r"PACE BING $b_{bp,700}$ [m$^{-1}$]")
        ax.set_title(
            f"BING vs. Argo\n"
            f"ρ={rho_b:.2f}  bias={bias_b:+.2f}  RMS={rms_b:.2f} (log10)",
            fontsize=9,
        )
        ax.legend(fontsize=7.5, framealpha=0.9)
        ax.grid(True, which="major", lw=0.4, alpha=0.5, color="#aaa")
        ax.set_axisbelow(True)
        ax.text(-0.12, 1.05, "(a)", transform=ax.transAxes, fontsize=11,
                fontweight="bold")

        # (b) GIOP vs Argo
        ax = axes[1]
        ax.scatter(df["bbp_argo"], df["bbp_giop700"], s=1.5, alpha=0.1,
                   color="#d6604d", linewidths=0, rasterized=True)
        ax.plot([lo, hi], [lo, hi], "k-", lw=1.2, label="1:1")
        ax.plot([lo, hi], [lo * med_ratio_g, hi * med_ratio_g], "r--", lw=1.2,
                label=f"Median ratio = {med_ratio_g:.2f}")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.set_xlabel(r"Argo $b_{bp,700}$ [m$^{-1}$]")
        ax.set_ylabel(r"PACE GIOP $b_{bp,700}$ [m$^{-1}$]")
        ax.set_title(
            f"GIOP vs. Argo\n"
            f"ρ={rho_g:.2f}  bias={bias_g:+.2f}  RMS={rms_g:.2f} (log10)",
            fontsize=9,
        )
        ax.legend(fontsize=7.5, framealpha=0.9)
        ax.grid(True, which="major", lw=0.4, alpha=0.5, color="#aaa")
        ax.set_axisbelow(True)
        ax.text(-0.12, 1.05, "(b)", transform=ax.transAxes, fontsize=11,
                fontweight="bold")

        # (c) Histogram overlay
        ax = axes[2]
        bins = np.arange(-1.5, 1.05, 0.05)
        ax.hist(df["delta_bing"].clip(-1.5, 1.0), bins=bins, color="#2166ac",
                alpha=0.6, label=f"BING  median={med_b:+.2f} ({pct_b:.0f}% > 0)")
        ax.hist(df["delta_giop"].clip(-1.5, 1.0), bins=bins, color="#d6604d",
                alpha=0.6, label=f"GIOP  median={med_g:+.2f} ({pct_g:.0f}% > 0)")
        ax.axvline(0, color="black", lw=0.8, ls="--")
        ax.axvline(med_b, color="#2166ac", lw=1.5)
        ax.axvline(med_g, color="#d6604d", lw=1.5)
        ax.set_xlabel(r"$\delta$ = (PACE $-$ Argo) / PACE")
        ax.set_ylabel("Count")
        ax.set_title(f"Distribution of relative bias\nn = {n:,}", fontsize=9)
        ax.legend(fontsize=7.5, framealpha=0.9)
        ax.grid(True, lw=0.4, alpha=0.5, color="#aaa")
        ax.set_axisbelow(True)
        ax.text(-0.12, 1.05, "(c)", transform=ax.transAxes, fontsize=11,
                fontweight="bold")

        fig.tight_layout()
        outpath = out or DEFAULT_OUT
        fig.savefig(outpath, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved → {outpath}  (n={n:,})")
        print(f"BING: median δ={med_b:+.3f}, {pct_b:.1f}% positive")
        print(f"GIOP: median δ={med_g:+.3f}, {pct_g:.1f}% positive")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    parser.add_argument("--parquet", default=None)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    df = load_data(db=args.db, parquet=args.parquet)
    print(f"Loaded {len(df):,} matched BING+GIOP matchups")
    make_figure(df, out=args.out)
