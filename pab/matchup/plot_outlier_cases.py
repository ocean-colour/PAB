"""
Figure 17: Case study of eight extreme outlier matchups where Argo >> PACE.

Selects matchups where PACE/Argo ratio < 0.1 (Argo > 10x PACE), one per float,
and produces a three-panel figure:
  (a) 1:1 scatter with outliers labeled A–H
  (b) Paired bar chart of Argo vs. PACE bbp700 per case
  (c) BING chi-squared vs. PACE/Argo ratio, colored by |latitude|

Usage:
    python plot_outlier_cases.py
    python plot_outlier_cases.py --db /path/to/pab_full.db --out /path/to/out.png
"""
import argparse
import sqlite3
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pab.config import DATA_DIR

DEFAULT_DB = Path(DATA_DIR) / "pab_full.db"
DEFAULT_PARQUET = Path(DATA_DIR) / "matchup_summary.parquet"
DEFAULT_OUT = Path(DATA_DIR) / "fig17_outlier_cases.png"
N_CASES = 8
RATIO_THRESHOLD = 0.1  # PACE/Argo ratio below which a matchup is an outlier


def load_data(db=None, parquet=None):
    db_path = db or DEFAULT_DB
    par_path = parquet or DEFAULT_PARQUET

    par = pd.read_parquet(par_path)
    par = par.dropna(subset=["bbp_argo", "bbp_bing"])
    par = par[(par["bbp_argo"] > 0) & (par["bbp_bing"] > 0)].copy()
    par["ratio"] = par["bbp_bing"] / par["bbp_argo"]

    con = sqlite3.connect(db_path)
    geo = pd.read_sql(
        "SELECT matchup_id, distance_km, dtime_hours FROM matchups", con
    )
    con.close()

    df = par.merge(geo, on="matchup_id", how="left")

    # Select worst N_CASES, one per float, ratio below threshold
    worst = (
        df[df["ratio"] < RATIO_THRESHOLD]
        .sort_values("ratio")
        .drop_duplicates(subset=["wmo"])
        .head(N_CASES)
        .reset_index(drop=True)
    )
    worst["label"] = [chr(65 + i) for i in range(len(worst))]
    normal = df[df["ratio"] >= 0.5]
    return df, worst, normal


def make_figure(df, worst, normal, out=None):
    RC = {
        "font.size": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "figure.dpi": 180, "axes.linewidth": 0.8,
    }

    with mpl.rc_context(RC):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.8))

        # (a) 1:1 scatter with labeled outliers
        ax = axes[0]
        lo, hi = 10 ** -5, 10 ** -1
        ax.scatter(normal["bbp_argo"], normal["bbp_bing"], s=2, alpha=0.1,
                   color="#2166ac", linewidths=0, rasterized=True)
        ax.scatter(worst["bbp_argo"], worst["bbp_bing"], s=65, color="#d6604d",
                   zorder=5, linewidths=0.6, edgecolors="black")
        for _, r in worst.iterrows():
            ax.annotate(r["label"], (r["bbp_argo"], r["bbp_bing"]),
                        fontsize=7.5, fontweight="bold",
                        xytext=(5, 4), textcoords="offset points")
        ax.plot([lo, hi], [lo, hi], "k-", lw=1.2)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.set_xlabel(r"Argo $b_{bp,700}$ [m$^{-1}$]")
        ax.set_ylabel(r"PACE BING $b_{bp,700}$ [m$^{-1}$]")
        ax.set_title(f"Case study outliers\n(Argo > 10x PACE, n={len(worst)})",
                     fontsize=9)
        ax.grid(True, which="major", lw=0.4, alpha=0.5, color="#aaa")
        ax.set_axisbelow(True)
        ax.text(-0.12, 1.05, "(a)", transform=ax.transAxes, fontsize=11,
                fontweight="bold")

        # (b) Paired bar chart
        ax = axes[1]
        x = np.arange(len(worst))
        w = 0.35
        ax.bar(x - w / 2, worst["bbp_argo"], w, color="#d6604d", alpha=0.85,
               label="Argo")
        ax.bar(x + w / 2, worst["bbp_bing"], w, color="#2166ac", alpha=0.85,
               label="PACE BING")
        ax.set_yscale("log")
        ax.set_xticks(x)
        ax.set_xticklabels(worst["label"])
        ax.set_xlabel("Case")
        ax.set_ylabel(r"$b_{bp,700}$ [m$^{-1}$]")
        ax.set_title(r"Argo vs. PACE $b_{bp,700}$ per case", fontsize=9)
        ax.legend(fontsize=8.5, framealpha=0.9)
        ax.grid(True, axis="y", lw=0.4, alpha=0.5, color="#aaa")
        ax.set_axisbelow(True)
        ax.text(-0.12, 1.05, "(b)", transform=ax.transAxes, fontsize=11,
                fontweight="bold")

        # (c) chi-sq vs ratio colored by |lat|
        ax = axes[2]
        sc = ax.scatter(
            worst["chisq"], worst["ratio"] * 100,
            c=worst["latitude"].abs(), cmap="plasma",
            s=85, zorder=5, edgecolors="black", linewidths=0.5,
            vmin=0, vmax=75,
        )
        for _, r in worst.iterrows():
            ax.annotate(r["label"], (r["chisq"], r["ratio"] * 100),
                        fontsize=7.5, fontweight="bold",
                        xytext=(5, 4), textcoords="offset points")
        ax.set_xlabel(r"BING $\chi^2$")
        ax.set_ylabel("PACE/Argo ratio (%)")
        ax.set_title("Fit quality vs. PACE/Argo ratio\ncolored by |latitude|",
                     fontsize=9)
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label("|Latitude| (deg)", fontsize=8)
        ax.grid(True, lw=0.4, alpha=0.5, color="#aaa")
        ax.set_axisbelow(True)
        ax.text(-0.12, 1.05, "(c)", transform=ax.transAxes, fontsize=11,
                fontweight="bold")

        fig.tight_layout()
        outpath = out or DEFAULT_OUT
        fig.savefig(outpath, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved → {outpath}")
        print("Outlier cases:")
        print(worst[["label", "wmo", "cycle", "latitude", "longitude",
                      "bbp_argo", "bbp_bing", "ratio", "chisq"]].to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    parser.add_argument("--parquet", default=None)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    df, worst, normal = load_data(db=args.db, parquet=args.parquet)
    print(f"Total matchups: {len(df):,}  |  Outliers (ratio < {RATIO_THRESHOLD}): "
          f"{(df['ratio'] < RATIO_THRESHOLD).sum()}")
    make_figure(df, worst, normal, out=args.out)
