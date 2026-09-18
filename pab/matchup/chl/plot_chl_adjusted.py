"""Adjusted vs. raw Argo Chl-a, and its effect on the PACE-vs-Argo bias.

New in this pass (chl_cdom_prompt_2.md Task 1(a)): the Stage 10 re-ingestion
added ``mld_summary.chla_adjusted`` (populated for 89.5% of profiles fleet-wide,
per chl_cdom_prompt_1.md Task 4). This answers Q10's deferred "second pass"
quantification — how much of the PACE-vs-Argo bias is attributable to the
missing delayed-mode/NPQ correction on the raw Argo reference.

Usage
-----
    python pab/matchup/chl/plot_chl_adjusted.py --outdir .
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups, rel_diff, valid_chl


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--outdir", type=Path, default=Path("."))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_raw_vs_adjusted(df, *, outfile=None, dpi: int = 200):
    """1:1 log-log scatter of raw vs. adjusted Argo Chl-a (the reference values alone)."""
    sub = df[
        df["chla_argo"].notna()
        & df["chla_adjusted"].notna()
        & (df["chla_argo"] > 0)
        & (df["chla_adjusted"] > 0)
    ].copy()
    log_raw = np.log10(sub["chla_argo"])
    log_adj = np.log10(sub["chla_adjusted"])
    ratio = sub["chla_adjusted"] / sub["chla_argo"]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(
        sub["chla_argo"],
        sub["chla_adjusted"],
        s=6,
        alpha=0.3,
        color="#08519c",
        linewidths=0,
    )
    lo = 10 ** (min(log_raw.min(), log_adj.min()) - 0.2)
    hi = 10 ** (max(log_raw.max(), log_adj.max()) + 0.2)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.plot([lo, hi], [lo, hi], "k-", lw=1.2, label="1:1")
    ax.set_xlabel(r"Raw Argo Chl-$a$ [mg m$^{-3}$]")
    ax.set_ylabel(r"Delayed-mode/real-time-adjusted Argo Chl-$a$ [mg m$^{-3}$]")
    ax.set_title(
        f"Raw vs. adjusted Argo Chl-a  (n = {len(sub)})\n"
        f"median adjusted/raw ratio = {np.median(ratio):.2f}"
    )
    ax.legend()
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_bias_raw_vs_adjusted(df, *, outfile=None, dpi: int = 200):
    """PACE-vs-Argo bias histogram: raw-Argo reference vs. adjusted-Argo reference."""
    sub = df[
        df["chla_adjusted"].notna()
        & (df["chla_adjusted"] > 0)
        & df["chl_bing"].notna()
        & (df["chl_bing"] > 0)
    ].copy()
    sub["rel_diff_adjusted"] = rel_diff(sub["chl_bing"], sub["chla_adjusted"])
    rd_raw = sub["rel_diff"].to_numpy(dtype=float)
    rd_adj = sub["rel_diff_adjusted"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bins = np.linspace(-1.5, 1.5, 32)
    ax.hist(
        rd_raw,
        bins=bins,
        color="#fc9272",
        alpha=0.55,
        density=True,
        label=f"vs. raw Argo (med={np.median(rd_raw):+.2f})",
    )
    ax.hist(
        rd_adj,
        bins=bins,
        color="#08519c",
        alpha=0.55,
        density=True,
        label=f"vs. adjusted Argo (med={np.median(rd_adj):+.2f})",
    )
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel("Relative difference  (PACE − Argo) / PACE")
    ax.set_ylabel("Density")
    ax.set_title(
        f"PACE-vs-Argo Chl-a bias: raw vs. adjusted reference  (n = {len(sub)})"
    )
    ax.legend(fontsize=9, frameon=False)
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
    n_adj = df["chla_adjusted"].notna().sum()
    print(
        f"{n_adj} of {len(df)} ({100 * n_adj / len(df):.1f}%) have a populated chla_adjusted"
    )
    args.outdir.mkdir(parents=True, exist_ok=True)

    plot_raw_vs_adjusted(
        df, outfile=args.outdir / "chl_raw_vs_adjusted_argo.png", dpi=args.dpi
    )
    plot_bias_raw_vs_adjusted(
        df, outfile=args.outdir / "chl_bias_raw_vs_adjusted.png", dpi=args.dpi
    )


if __name__ == "__main__":
    main()
