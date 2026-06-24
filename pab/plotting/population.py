"""Population figures (Stage 6).

Across-matchup views: the satellite-vs-in-situ ``b_bp`` log-log scatter (with
1:1 and median-ratio offset lines), the BING-vs-NASA-L2-IOP comparison (the same
plot on two satellite columns), and a matchup map. Pure Matplotlib/NumPy on a
gathered :class:`pandas.DataFrame` (see :mod:`pab.metrics.compare`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pab.metrics.compare import log_comparison

SIZE_BUDGET = 100 * 1024


def comparison_scatter(
    df,
    sat_col: str,
    insitu_col: str,
    *,
    label: str = "b_bp",
    unit: str = "m$^{-1}$",
    outfile=None,
    dpi: int = 100,
):
    """Log-log scatter of ``sat_col`` vs ``insitu_col`` with 1:1 + median-ratio.

    Annotates the panel with the :func:`~pab.metrics.compare.log_comparison`
    summary (n, median ratio, Spearman ρ, log bias/RMS).

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    import matplotlib.pyplot as plt

    sat = np.asarray(df[sat_col], dtype=float)
    insitu = np.asarray(df[insitu_col], dtype=float)
    stats = log_comparison(sat, insitu)
    ok = np.isfinite(sat) & np.isfinite(insitu) & (sat > 0) & (insitu > 0)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.loglog(insitu[ok], sat[ok], "o", ms=5, color="C0", alpha=0.8)
    if ok.any():
        lo = float(np.min([insitu[ok].min(), sat[ok].min()])) * 0.7
        hi = float(np.max([insitu[ok].max(), sat[ok].max()])) * 1.4
        line = np.array([lo, hi])
        ax.plot(line, line, "k-", lw=1, label="1:1")
        if np.isfinite(stats["median_ratio"]):
            ax.plot(
                line,
                stats["median_ratio"] * line,
                "C3--",
                lw=1,
                label=f"median ratio = {stats['median_ratio']:.2f}",
            )
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
    ax.set_xlabel(f"in-situ {label} [{unit}]")
    ax.set_ylabel(f"satellite {label} [{unit}]")
    ax.set_title(
        f"n={stats['n']}  ρ={stats['spearman']:.2f}  "
        f"bias={stats['log_bias']:+.2f}  RMS={stats['log_rms']:.2f} (log10)",
        fontsize=9,
    )
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    return _finish(fig, outfile, dpi)


def matchup_map(df, *, color_col: str | None = None, outfile=None, dpi: int = 100):
    """Scatter the matchup float positions (optionally coloured by a column)."""
    import matplotlib.pyplot as plt

    lon = np.asarray(df["longitude"], dtype=float)
    lat = np.asarray(df["latitude"], dtype=float)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    if color_col and color_col in df:
        sc = ax.scatter(
            lon, lat, c=np.asarray(df[color_col], dtype=float), cmap="viridis", s=40
        )
        fig.colorbar(sc, ax=ax, label=color_col)
    else:
        ax.scatter(lon, lat, s=40, color="C0")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("matchup locations", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _finish(fig, outfile, dpi)


def _finish(fig, outfile, dpi):
    import matplotlib.pyplot as plt

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return outfile
    return fig
