"""Chl-a bias stratified by processing DAC (data center) — AOML vs. the rest.

New in this pass (chl_cdom_prompt_2.md Task 1(b)): the Stage 10 re-ingestion
populated ``floats.data_center`` (612/881 floats, or 617/881 once the 8
fully-failed floats are externally reconciled — see chl_cdom_prompt_1.md's
Task 4 report). This tests whether the PACE-vs-Argo bias signature differs by
processing center, e.g. a QC/calibration-convention difference between AOML
and the rest of the fleet (Coriolis/INCOIS/MEDS/CSIRO/BODC/CSIO/JMA).

Usage
-----
    python pab/matchup/chl/plot_chl_dac.py --outdir .
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
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_by_dac(df, *, outfile=None, dpi: int = 200):
    """Rel-diff distribution: AOML-processed floats vs. all other DACs."""
    known = df[df["data_center"].notna()].copy()
    aoml = known.loc[known["is_aoml"], "rel_diff"].to_numpy(dtype=float)
    other = known.loc[~known["is_aoml"], "rel_diff"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bins = np.linspace(-1.5, 1.5, 32)
    ax.hist(
        other,
        bins=bins,
        color="#969696",
        alpha=0.55,
        density=True,
        label=f"Other DACs (n={len(other)}, med={np.median(other):+.2f})",
    )
    ax.hist(
        aoml,
        bins=bins,
        color="#e6550d",
        alpha=0.55,
        density=True,
        label=f"AOML (n={len(aoml)}, med={np.median(aoml):+.2f})",
    )
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel("Relative difference  (PACE − Argo) / PACE")
    ax.set_ylabel("Density")
    ax.set_title(f"Chl-a bias by processing DAC  (n = {len(known)} with known DAC)")
    ax.legend(fontsize=9, frameon=False)
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_by_project(df, *, outfile=None, dpi: int = 200, top_n: int = 8):
    """Rel-diff by ``data_center`` code, for every DAC with enough matchups to plot."""
    known = df[df["data_center"].notna()].copy()
    counts = known["data_center"].value_counts()
    dacs = [d for d in counts.index if counts[d] >= 20][:top_n]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
    cmap = plt.get_cmap("tab10")
    for i, dac in enumerate(dacs):
        sub = known.loc[known["data_center"] == dac, "rel_diff"]
        jit = np.random.default_rng(i).uniform(-0.15, 0.15, len(sub))
        ax.scatter(i + jit, sub.values, s=6, alpha=0.25, color=cmap(i), linewidths=0)
        ax.plot(
            [i - 0.25, i + 0.25],
            [sub.median(), sub.median()],
            color=cmap(i),
            lw=2.5,
            solid_capstyle="round",
            label=f"{dac} (n={len(sub)}, med={sub.median():+.2f})",
        )
    ax.set_xticks(range(len(dacs)))
    ax.set_xticklabels(dacs, fontsize=9)
    ax.set_ylabel(r"$(Chl^{\rm PACE} - Chl^{\rm Argo})\,/\,Chl^{\rm PACE}$")
    ax.set_title("Chl-a relative difference by DAC  (DACs with n ≥ 20 matchups)")
    ax.legend(fontsize=7.5, loc="lower right", ncol=2)
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
    n_known = df["data_center"].notna().sum()
    print(
        f"{n_known} of {len(df)} ({100 * n_known / len(df):.1f}%) have a known data_center"
    )
    args.outdir.mkdir(parents=True, exist_ok=True)

    plot_by_dac(df, outfile=args.outdir / "chl_reldiff_by_dac_aoml.png", dpi=args.dpi)
    plot_by_project(
        df, outfile=args.outdir / "chl_reldiff_by_dac_all.png", dpi=args.dpi
    )


if __name__ == "__main__":
    main()
