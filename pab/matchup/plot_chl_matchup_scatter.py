"""
1:1 scatter of PACE BING Chl-a vs. Argo Chl-a from a PAB SQLite database.

Usage:
    python plot_chl_matchup_scatter.py
    python plot_chl_matchup_scatter.py --db /path/to/pab.db
    python plot_chl_matchup_scatter.py --db /path/to/pab.db --out /path/to/output.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from pab.config import DATA_DIR
from pab.db.store import Store
from pab.metrics.compare import gather_matchups

DEFAULT_DB  = Path(DATA_DIR) / "pab.db"
DEFAULT_OUT = Path(DATA_DIR) / "chl_pace_vs_argo_scatter.png"

# Upper ceiling for Chl-a (mg m⁻³); values above this are likely sensor artifacts.
CHl_MAX = 100.0


def load_data(db: Path = DEFAULT_DB):
    """Load Chl-a matchup data from the PAB database."""
    with Store.open(db, create=False) as store:
        df = gather_matchups(store)
    before = len(df)
    df = df.dropna(subset=["chla_argo", "chl_bing"]).copy()
    df = df[(df["chla_argo"] > 0) & (df["chl_bing"] > 0)].copy()
    df = df[(df["chla_argo"] <= CHl_MAX) & (df["chl_bing"] <= CHl_MAX)].copy()
    dropped = before - len(df)
    if dropped:
        print(f"  Dropped {dropped} rows (NaN / non-positive / > {CHl_MAX} mg m⁻³)")
    return df


def make_scatter(df, out=DEFAULT_OUT):
    log_a = np.log10(df["chla_argo"])
    log_b = np.log10(df["chl_bing"])
    rho, _ = stats.spearmanr(df["chla_argo"], df["chl_bing"])
    bias = np.mean(log_b - log_a)
    rms  = np.sqrt(np.mean((log_b - log_a) ** 2))
    med_ratio = np.median(df["chl_bing"] / df["chla_argo"])

    rc = {
        "font.size": 10, "axes.labelsize": 10,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 9, "figure.dpi": 150,
        "axes.spines.top": True, "axes.spines.right": True,
    }

    with mpl.rc_context(rc):
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.scatter(df["chla_argo"], df["chl_bing"],
                   color="#2ca25f", s=6, alpha=0.35, linewidths=0)

        lo = 10 ** (min(log_a.min(), log_b.min()) - 0.2)
        hi = 10 ** (max(log_a.max(), log_b.max()) + 0.2)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_xscale("log")
        ax.set_yscale("log")
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
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    df = load_data(db=args.db)
    print(f"Loaded {len(df)} matchups")
    make_scatter(df, out=args.out)
