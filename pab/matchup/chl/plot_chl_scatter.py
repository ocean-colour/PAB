"""1:1 log-log scatter of PACE BING Chl-a vs. Argo Chl-a.

Absorbed and generalized from the original ``pab/matchup/plot_chl_matchup_scatter.py``
(hardcoded ``/Users/alliejames/...`` paths replaced with :data:`pab.config.DATA_DIR`;
now built on the shared :mod:`pab.matchup.chl.data` loader, so it carries the
full N ≈ 14.6k matchup set with geometry/strata joins, not just the flat parquet).

Usage
-----
    python pab/matchup/chl/plot_chl_scatter.py
    python pab/matchup/chl/plot_chl_scatter.py --db /path/to/pab.db --out scatter.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups, valid_chl


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("chl_pace_vs_argo_scatter.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_chl_scatter(df, *, outfile=None, dpi: int = 200):
    """Log-log scatter of ``chl_bing`` vs. ``chla_argo``, colored by relative difference.

    Args:
        df: Frame from :func:`pab.matchup.chl.data.load_chl_matchups`
            (already filtered to valid rows, e.g. via :func:`valid_chl`).
        outfile: Save path, or ``None`` to return the Figure.
        dpi: Output resolution.

    Returns:
        Matplotlib Figure or written Path.
    """
    log_a = np.log10(df["chla_argo"])
    log_b = np.log10(df["chl_bing"])
    n = len(df)
    rho, _ = stats.spearmanr(df["chla_argo"], df["chl_bing"])
    log_bias = np.mean(log_b - log_a)
    log_rms = np.sqrt(np.mean((log_b - log_a) ** 2))
    med_ratio = np.median(df["chl_bing"] / df["chla_argo"])

    mpl.rcParams.update(
        {
            "font.size": 10,
            "axes.labelsize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 9,
            "figure.dpi": 150,
        }
    )

    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    sc = ax.scatter(
        df["chla_argo"],
        df["chl_bing"],
        c=df["rel_diff"].clip(-1, 1),
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        s=6,
        alpha=0.4,
        linewidths=0,
    )

    lo = 10 ** (min(log_a.min(), log_b.min()) - 0.2)
    hi = 10 ** (max(log_a.max(), log_b.max()) + 0.2)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.plot([lo, hi], [lo, hi], "k-", lw=1.2, label="1:1")
    ax.plot(
        [lo, hi],
        [lo * med_ratio, hi * med_ratio],
        "k--",
        lw=1.2,
        label=f"median ratio = {med_ratio:.2f}",
    )
    ax.grid(True, which="major", lw=0.5, alpha=0.6, color="#aaaaaa")
    ax.grid(True, which="minor", lw=0.3, alpha=0.4, color="#cccccc")
    ax.set_axisbelow(True)
    ax.set_xlabel(r"Argo Chl-$a$ [mg m$^{-3}$]")
    ax.set_ylabel(r"PACE BING Chl-$a$ [mg m$^{-3}$]")
    ax.set_title(
        r"Argo Chl-$a$ vs. PACE Chl-$a$"
        + f"  (n = {n})\n"
        + rf"$\rho$={rho:.2f}  log-bias={log_bias:+.2f}  log-RMS={log_rms:.2f}",
        fontsize=9,
    )
    cbar = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Relative difference (PACE − Argo) / PACE", fontsize=9)
    ax.legend(framealpha=0.9)
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
    df = valid_chl(df)
    print(f"Loaded {len(df)} valid Chl-a matchups")
    plot_chl_scatter(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
