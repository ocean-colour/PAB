"""Chl-specific diagnostics (chl_cdom_matchups.md Plan, figure-set item 7):

1. Relative difference vs. Chl magnitude — is the retrieval bias
   concentration-dependent?
2. Chl rel-diff vs. bbp700 rel-diff, per matchup — are the two BING retrieval
   biases correlated (shared cause), or independent?
3. Chl rel-diff vs. the fitted CDOM/detrital amplitude (``BING_ExpBPow_Adg``) —
   a zero-extra-data probe of the CDOM/detrital-absorption-aliasing hypothesis
   on the Bricaud phytoplankton term.

Usage
-----
    python pab/matchup/chl/plot_chl_diagnostics.py --outdir .
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups, valid_chl
from pab.matchup.chl.plot_chl_stratification import _octile_binned


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--outdir", type=Path, default=Path("."))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_vs_magnitude(df, *, outfile=None, dpi: int = 200):
    """Rel-diff vs. Argo Chl-a magnitude (log-x), with octile-bin medians."""
    x = df["chla_argo"].to_numpy(dtype=float)
    y = df["rel_diff"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.scatter(
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
    mid, bmed = _octile_binned(np.log10(x), y)
    ax.plot(
        10 ** np.asarray(mid),
        bmed,
        "ko-",
        ms=6,
        lw=1.5,
        label="octile medians",
        zorder=5,
    )
    ax.set_xscale("log")
    ax.set_xlabel(r"Argo Chl-$a$ [mg m$^{-3}$]")
    ax.set_ylabel(r"$(Chl^{\rm PACE} - Chl^{\rm Argo})\,/\,Chl^{\rm PACE}$")
    ax.set_title(f"Chl-a relative difference vs. Chl-a magnitude  (n = {len(df)})")
    ax.legend(fontsize=9)
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_vs_bbp_bias(df, *, outfile=None, dpi: int = 200):
    """Chl rel-diff vs. bbp700 rel-diff, per matchup — shared-cause probe."""
    sub = df[df["bbp_rel_diff"].notna() & np.isfinite(df["bbp_rel_diff"])].copy()
    x = sub["bbp_rel_diff"].to_numpy(dtype=float)
    y = sub["rel_diff"].to_numpy(dtype=float)
    rho, _ = stats.spearmanr(x, y)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(x, y, s=8, alpha=0.3, color="#6a51a3", linewidths=0)
    ax.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
    ax.axvline(0, color="k", lw=0.8, ls="--", alpha=0.5)
    lim = 1.6
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel(
        r"bbp700 rel. diff.  $(b_{bp}^{\rm PACE} - b_{bp}^{\rm Argo})/b_{bp}^{\rm PACE}$"
    )
    ax.set_ylabel(
        r"Chl-a rel. diff.  $(Chl^{\rm PACE} - Chl^{\rm Argo})/Chl^{\rm PACE}$"
    )
    ax.set_title(
        f"Chl-a bias vs. bbp700 bias, per matchup  (n = {len(sub)}, "
        + rf"$\rho$={rho:.2f})"
    )
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_vs_adg(df, *, outfile=None, dpi: int = 200):
    """Chl rel-diff vs. the fitted CDOM/detrital absorption amplitude (``Adg``)."""
    sub = df[
        df["adg_bing"].notna() & np.isfinite(df["adg_bing"]) & (df["adg_bing"] > 0)
    ].copy()
    x = sub["adg_bing"].to_numpy(dtype=float)
    y = sub["rel_diff"].to_numpy(dtype=float)
    rho, _ = stats.spearmanr(x, y)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.scatter(
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
    mid, bmed = _octile_binned(np.log10(x), y)
    ax.plot(
        10 ** np.asarray(mid),
        bmed,
        "ko-",
        ms=6,
        lw=1.5,
        label="octile medians",
        zorder=5,
    )
    ax.set_xscale("log")
    ax.set_xlabel(r"BING fitted CDOM+detrital amplitude $A_{dg}$ [m$^{-1}$]")
    ax.set_ylabel(r"$(Chl^{\rm PACE} - Chl^{\rm Argo})\,/\,Chl^{\rm PACE}$")
    ax.set_title(
        f"Chl-a bias vs. fitted CDOM/detrital amplitude  (n = {len(sub)}, "
        rf"$\rho$={rho:.2f})"
    )
    ax.legend(fontsize=9)
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

    plot_vs_magnitude(
        df, outfile=args.outdir / "chl_reldiff_vs_magnitude.png", dpi=args.dpi
    )
    plot_vs_bbp_bias(df, outfile=args.outdir / "chl_bias_vs_bbp_bias.png", dpi=args.dpi)
    plot_vs_adg(df, outfile=args.outdir / "chl_reldiff_vs_adg.png", dpi=args.dpi)


if __name__ == "__main__":
    main()
