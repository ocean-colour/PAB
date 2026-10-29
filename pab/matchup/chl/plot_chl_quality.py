"""Chl-a bias in the highest-quality subset, plus the free data-mode (R/A/D) panel.

Mirrors ``plot_bbp_matchup_map_clean.py``'s cloud-cover/chisq quality filter,
generalized to Chl-a and to a non-map (rel-diff distribution) comparison —
plus one extra panel this pass makes possible: stratifying by
``chla_data_mode`` (the per-parameter R/A/D flag added in the Stage 10
re-ingestion; see chl_cdom_matchups.md Q11). This is a real, populated field
(89.5% of profiles have an adjusted/delayed value), unlike the coarse
whole-profile ``profiles.data_mode`` which is NULL for nearly all BGC profiles
(see chl_cdom_prompt_1.md Task 2's finding) — kept here as a secondary,
mostly-empty reference column only.

Usage
-----
    python pab/matchup/chl/plot_chl_quality.py --outdir .
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
    p.add_argument("--outdir", type=Path, default=Path("."))
    p.add_argument(
        "--cc", type=float, default=50.0, help="Max cloud cover %% (default 50)"
    )
    p.add_argument(
        "--chisq", type=float, default=1.2, help="Max BING reduced chi-squared"
    )
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_quality_subset(
    df, *, cc_thresh: float, chisq_thresh: float, outfile=None, dpi: int = 200
):
    """Rel-diff distribution: all valid matchups vs. the high-quality subset."""
    cc = df["cloud_cover"].to_numpy(dtype=float)
    chi = df["chisq"].to_numpy(dtype=float)
    good = np.isfinite(cc) & np.isfinite(chi) & (cc < cc_thresh) & (chi < chisq_thresh)
    all_rd = df["rel_diff"].to_numpy(dtype=float)
    good_rd = df.loc[good, "rel_diff"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bins = np.linspace(-1.5, 1.5, 32)
    ax.hist(
        all_rd,
        bins=bins,
        color="#a1d99b",
        alpha=0.5,
        density=True,
        label=f"All (n={len(df)}, med={np.median(all_rd):+.2f})",
    )
    ax.hist(
        good_rd,
        bins=bins,
        color="#00441b",
        alpha=0.6,
        density=True,
        label=f"Quality-filtered (n={good.sum()}, med={np.median(good_rd):+.2f})",
    )
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel("Relative difference  (PACE − Argo) / PACE")
    ax.set_ylabel("Density")
    ax.set_title(
        f"Chl-a bias, all vs. high-quality subset\n(cloud cover < {cc_thresh:.0f}%, BING chi-sq_r < {chisq_thresh})"
    )
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_by_data_mode(df, *, outfile=None, dpi: int = 200):
    """Rel-diff by Argo Chl-a data mode (``chla_data_mode``: R/A/D)."""
    order = ["R", "A", "D"]
    labels = {"R": "Real-time", "A": "Real-time adjusted", "D": "Delayed-mode"}
    colors = {"R": "#fc8d59", "A": "#91bfdb", "D": "#2166ac"}

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
    for i, mode in enumerate(order):
        sub = df.loc[df["chla_data_mode"] == mode, "rel_diff"]
        if sub.empty:
            continue
        jit = np.random.default_rng(i).uniform(-0.15, 0.15, len(sub))
        ax.scatter(
            i + jit, sub.values, s=8, alpha=0.3, color=colors[mode], linewidths=0
        )
        ax.plot(
            [i - 0.25, i + 0.25],
            [sub.median(), sub.median()],
            color=colors[mode],
            lw=2.5,
            solid_capstyle="round",
            label=f"{labels[mode]} (n={len(sub)}, med={sub.median():+.2f})",
        )
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([labels[m] for m in order], fontsize=9)
    ax.set_ylabel(r"$(Chl^{\rm PACE} - Chl^{\rm Argo})\,/\,Chl^{\rm PACE}$")
    ax.set_title(
        f"Chl-a relative difference by Argo data mode  (n = {df['chla_data_mode'].isin(order).sum()})"
    )
    ax.legend(fontsize=8, loc="lower right")
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

    plot_quality_subset(
        df,
        cc_thresh=args.cc,
        chisq_thresh=args.chisq,
        outfile=args.outdir / "chl_reldiff_quality_subset.png",
        dpi=args.dpi,
    )
    plot_by_data_mode(
        df, outfile=args.outdir / "chl_reldiff_by_data_mode.png", dpi=args.dpi
    )


if __name__ == "__main__":
    main()
