"""
Figures 7 and 8: Relative bias δ as a function of PACE and Argo bbp700.

Fig 7 (PACE-normalized):  δ = (PACE − Argo) / PACE  vs  PACE bbp  and  Argo bbp
Fig 8 (Argo-normalized):  δ = (Argo − PACE)  / Argo  vs  Argo bbp  and  PACE bbp

Usage:
    python plot_delta_vs_bbp.py                   # generates both figures
    python plot_delta_vs_bbp.py --which pace      # Fig 7 only
    python plot_delta_vs_bbp.py --which argo      # Fig 8 only
    python plot_delta_vs_bbp.py --parquet /path/to/matchup_summary.parquet
    python plot_delta_vs_bbp.py --out-dir /path/to/output/
"""
import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from pab.config import DATA_DIR

DEFAULT_PARQUET = Path(DATA_DIR) / "matchup_summary.parquet"
DEFAULT_OUT = Path(DATA_DIR)


def load_data(parquet=None):
    path = parquet or DEFAULT_PARQUET
    df = pd.read_parquet(path)
    df = df.dropna(subset=["bbp_argo", "bbp_bing"])
    df = df[(df["bbp_argo"] > 0) & (df["bbp_bing"] > 0)].copy()
    return df


def _pval_str(p):
    if p < 1e-300:
        return "p < 10⁻³⁰⁰"
    elif p < 0.001:
        return "p < 0.001"
    else:
        return f"p = {p:.3f}"


def plot_pace_normalized(df, out=None):
    """Fig 7: δ = (PACE − Argo) / PACE vs PACE bbp (left) and Argo bbp (right)."""
    df = df.copy()
    df["delta"] = (df["bbp_bing"] - df["bbp_argo"]) / df["bbp_bing"]
    df = df[df["delta"].between(-1.5, 1.0)]

    RC = {
        "font.size": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "figure.dpi": 180, "axes.linewidth": 0.8,
    }
    panels = [
        ("bbp_bing", r"PACE $b_{bp,700}$ [m$^{-1}$]", "blue"),
        ("bbp_argo", r"Argo $b_{bp,700}$ [m$^{-1}$]", "red"),
    ]

    with mpl.rc_context(RC):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
        for ax, (xcol, xlabel, color) in zip(axes, panels):
            x = df[xcol].values
            y = df["delta"].values
            rho, p = stats.spearmanr(x, y)
            ax.scatter(x, y, s=1.5, alpha=0.15, color=color, linewidths=0,
                       rasterized=True)
            ax.axhline(0, color="black", lw=0.8, ls="--")
            ax.set_xscale("log")
            ax.set_xlabel(xlabel)
            ax.set_ylabel(r"$\delta$ = (PACE $-$ Argo) / PACE")
            ax.set_ylim(-1.05, 1.05)
            ax.set_title(
                f"{xlabel.split('[')[0].strip()}\n"
                f"Spearman ρ = {rho:.2f}, {_pval_str(p)}",
                fontsize=9,
            )
            ax.grid(True, lw=0.4, alpha=0.5, color="#cccccc")
            ax.set_axisbelow(True)

        axes[0].text(-0.12, 1.05, "(a)", transform=axes[0].transAxes,
                     fontsize=11, fontweight="bold")
        axes[1].text(-0.12, 1.05, "(b)", transform=axes[1].transAxes,
                     fontsize=11, fontweight="bold")
        fig.tight_layout()

        outpath = (Path(out) / "fig7_delta_vs_bbp_pace.png") if out else \
                  DEFAULT_OUT / "fig7_delta_vs_bbp_pace.png"
        fig.savefig(outpath, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved → {outpath}")


def plot_argo_normalized(df, out=None):
    """Fig 8: δ = (Argo − PACE) / Argo vs Argo bbp (left) and PACE bbp (right)."""
    df = df.copy()
    df["delta"] = (df["bbp_argo"] - df["bbp_bing"]) / df["bbp_argo"]
    df = df[df["delta"].between(-1.5, 1.0)]

    # Clip x-axes at 99th percentile to avoid extreme outliers stretching axis
    xmax_argo = np.percentile(df["bbp_argo"], 99)
    xmax_bing = np.percentile(df["bbp_bing"], 99)

    RC = {
        "font.size": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "figure.dpi": 180, "axes.linewidth": 0.8,
    }
    panels = [
        ("bbp_argo", r"Argo $b_{bp,700}$ [m$^{-1}$]", "red", xmax_argo),
        ("bbp_bing", r"PACE BING $b_{bp,700}$ [m$^{-1}$]", "blue", xmax_bing),
    ]

    with mpl.rc_context(RC):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
        for ax, (xcol, xlabel, color, xmax) in zip(axes, panels):
            x = df[xcol].values
            y = df["delta"].values
            rho, p = stats.spearmanr(x, y)
            ax.scatter(x, y, s=1.5, alpha=0.15, color=color, linewidths=0,
                       rasterized=True)
            ax.axhline(0, color="black", lw=0.8, ls="--")
            ax.set_xlabel(xlabel)
            ax.set_ylabel(r"$\delta$ = (Argo $-$ PACE) / Argo")
            ax.set_xlim(0, xmax)
            ax.set_ylim(-1.05, 1.05)
            ax.set_title(
                f"{xlabel.split('[')[0].strip()}\n"
                f"Spearman ρ = {rho:.2f}, {_pval_str(p)}",
                fontsize=9,
            )
            ax.grid(True, lw=0.4, alpha=0.5, color="#cccccc")
            ax.set_axisbelow(True)

        axes[0].text(-0.12, 1.05, "(a)", transform=axes[0].transAxes,
                     fontsize=11, fontweight="bold")
        axes[1].text(-0.12, 1.05, "(b)", transform=axes[1].transAxes,
                     fontsize=11, fontweight="bold")
        fig.tight_layout()

        outpath = (Path(out) / "fig8_delta_vs_bbp_argo.png") if out else \
                  DEFAULT_OUT / "fig8_delta_vs_bbp_argo.png"
        fig.savefig(outpath, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved → {outpath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--which", choices=["pace", "argo", "both"],
                        default="both")
    args = parser.parse_args()

    df = load_data(parquet=args.parquet)
    print(f"Loaded {len(df):,} matchups")

    if args.which in ("pace", "both"):
        plot_pace_normalized(df, out=args.out_dir)
    if args.which in ("argo", "both"):
        plot_argo_normalized(df, out=args.out_dir)
