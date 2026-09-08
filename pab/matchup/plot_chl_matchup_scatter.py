"""
1:1 scatter of PACE BING Chl-a vs. Argo Chl-a from matchup_summary.parquet.

Usage:
    python plot_chl_matchup_scatter.py
    python plot_chl_matchup_scatter.py --parquet /path/to/matchup_summary.parquet
    python plot_chl_matchup_scatter.py --out /path/to/output.png
"""
import argparse
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy import stats

DEFAULT_PARQUET = "/Users/alliejames/Documents/summer 2026/data/PAB/matchup_summary.parquet"
DEFAULT_OUT     = "/Users/alliejames/Documents/summer 2026/data/PAB/chl_pace_vs_argo_scatter.png"


def load_data(parquet=None):
    import pandas as pd
    path = parquet or DEFAULT_PARQUET
    df = pd.read_parquet(path)
    df = df.dropna(subset=["chla_argo", "chl_bing"]).copy()
    df = df[(df["chla_argo"] > 0) & (df["chl_bing"] > 0)].copy()
    df = df[(df["chla_argo"] <= 100) & (df["chl_bing"] <= 100)].copy()
    return df


def make_scatter(df, out=DEFAULT_OUT):
    log_a = np.log10(df["chla_argo"])
    log_b = np.log10(df["chl_bing"])
    n = len(df)
    rho, _ = stats.spearmanr(df["chla_argo"], df["chl_bing"])
    bias = np.mean(log_b - log_a)
    rms  = np.sqrt(np.mean((log_b - log_a) ** 2))
    med_ratio = np.median(df["chl_bing"] / df["chla_argo"])

    mpl.rcParams.update({
        "font.size": 10, "axes.labelsize": 10,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 9, "figure.dpi": 150,
        "axes.spines.top": True, "axes.spines.right": True,
    })

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(df["chla_argo"], df["chl_bing"],
               color="#2ca25f", s=6, alpha=0.35, linewidths=0)

    lo = 10 ** (min(log_a.min(), log_b.min()) - 0.2)
    hi = 10 ** (max(log_a.max(), log_b.max()) + 0.2)
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.plot([lo, hi], [lo, hi], "k-", lw=1.2, label="1:1")
    ax.plot([lo, hi], [lo * med_ratio, hi * med_ratio], "r--", lw=1.2,
            label=f"median ratio = {med_ratio:.2f}")
    ax.grid(True, which="major", lw=0.5, alpha=0.6, color="#aaaaaa")
    ax.grid(True, which="minor", lw=0.3, alpha=0.4, color="#cccccc")
    ax.set_axisbelow(True)
    ax.set_xlabel(r"Argo Chl-$a$ [mg m$^{-3}$]")
    ax.set_ylabel(r"PACE BING Chl-$a$ [mg m$^{-3}$]")
    ax.set_title(
        r"Argo Chl-$a$ vs. PACE Chl-$a$" + "\n" +
        f"ρ={rho:.2f}  bias={bias:+.2f}  RMS={rms:.2f} (log10)",
        fontsize=9
    )
    ax.legend(framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", default=None)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    df = load_data(parquet=args.parquet)
    print(f"Loaded {len(df)} matchups")
    make_scatter(df, out=args.out)
