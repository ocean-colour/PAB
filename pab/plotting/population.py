"""Population figures (Stage 6).

Across-matchup views: the satellite-vs-in-situ ``b_bp`` log-log scatter (with
1:1 and median-ratio offset lines), the BING-vs-NASA-L2-IOP comparison (the same
plot on two satellite columns), a matchup map, and a one-column histogram
(used for the free ``B_p``). Pure Matplotlib/NumPy on a
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
    xlabel: str | None = None,
    ylabel: str | None = None,
    clip_percentile: float | None = None,
):
    """Log-log scatter of ``sat_col`` vs ``insitu_col`` with 1:1 + median-ratio.

    Annotates the panel with the :func:`~pab.metrics.compare.log_comparison`
    summary (n, median ratio, Spearman ρ, log bias/RMS).

    Args:
        xlabel, ylabel: Full axis-label overrides for pairings that are not
            satellite-vs-in-situ (e.g. BING vs NASA GIOP); default to
            ``"in-situ {label} [{unit}]"`` / ``"satellite {label} [{unit}]"``.
        clip_percentile: Set the axis range from this central percentile range
            (e.g. ``99`` → 0.5th–99.5th) instead of from the data extremes. For
            a population with a handful of non-physical retrievals, autoscaling
            squashes every real point into a corner. The off-scale points are
            **counted in the title, not removed** — they stay in the statistics,
            and the panel says how many are outside the axes, so clipping makes
            the figure readable without hiding a failure.

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
    offscale = 0
    if ok.any():
        if clip_percentile:
            edge = (100.0 - float(clip_percentile)) / 2.0
            both = np.concatenate([insitu[ok], sat[ok]])
            lo = float(np.percentile(both, edge)) * 0.7
            hi = float(np.percentile(both, 100.0 - edge)) * 1.4
            offscale = int(
                np.count_nonzero(
                    (insitu[ok] < lo) | (insitu[ok] > hi)
                    | (sat[ok] < lo) | (sat[ok] > hi)
                )
            )
        else:
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
    ax.set_xlabel(xlabel or f"in-situ {label} [{unit}]")
    ax.set_ylabel(ylabel or f"satellite {label} [{unit}]")
    ax.set_title(
        f"n={stats['n']}  ρ={stats['spearman']:.2f}  "
        f"bias={stats['log_bias']:+.2f}  RMS={stats['log_rms']:.2f} (log10)"
        + (f"  [{offscale} off-scale]" if offscale else ""),
        fontsize=9,
    )
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    return _finish(fig, outfile, dpi)


def ratio_vs_level(
    df,
    num_col: str,
    den_col: str,
    *,
    outfile=None,
    dpi: int = 100,
    nbins: int = 12,
    min_per_bin: int = 20,
    xlabel: str | None = None,
    ylabel: str | None = None,
):
    """Median ``num/den`` ratio against the magnitude of ``den``, log-binned.

    A single population median hides a ratio that varies systematically with
    the signal level, and a reader will otherwise take it as a correction
    factor. This plots the ratio *as a function of* the baseline value, with
    the interquartile band, so the trend is the result rather than a footnote.

    Bins holding fewer than ``min_per_bin`` points are dropped: a median of
    three points plotted beside a median of three thousand reads as the same
    kind of statement, and it is not.

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    import matplotlib.pyplot as plt

    num = np.asarray(df[num_col], dtype=float)
    den = np.asarray(df[den_col], dtype=float)
    ok = np.isfinite(num) & np.isfinite(den) & (num > 0) & (den > 0)
    num, den = num[ok], den[ok]
    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    if num.size >= min_per_bin:
        edges = np.logspace(
            np.log10(np.percentile(den, 0.5)),
            np.log10(np.percentile(den, 99.5)),
            nbins + 1,
        )
        xs, med, lo, hi, ns = [], [], [], [], []
        for a, b in zip(edges[:-1], edges[1:], strict=False):
            m = (den >= a) & (den < b)
            if m.sum() < min_per_bin:
                continue
            r = num[m] / den[m]
            xs.append(float(np.sqrt(a * b)))
            q1, q2, q3 = np.percentile(r, [25, 50, 75])
            med.append(q2)
            lo.append(q1)
            hi.append(q3)
            ns.append(int(m.sum()))
        if xs:
            ax.fill_between(xs, lo, hi, color="C0", alpha=0.22, label="IQR")
            ax.plot(xs, med, "o-", color="C0", lw=1.6, ms=5, label="median ratio")
            ax.set_title(
                f"{len(xs)} bins, {sum(ns):,} matchups "
                f"({min(ns)}-{max(ns)} per bin)",
                fontsize=9,
            )
        ax.axhline(1.0, color="k", lw=1, ls="-", label="no change")
        ax.set_xscale("log")
        ax.set_yscale("log")
        # Over a 2-3 decade span Matplotlib labels the MINOR log ticks too and
        # they overlap into an unreadable smear. Decade majors only.
        from matplotlib.ticker import LogLocator, NullFormatter

        ax.xaxis.set_major_locator(LogLocator(base=10.0))
        ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel(xlabel or den_col)
    ax.set_ylabel(ylabel or f"{num_col} / {den_col}")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    return _finish(fig, outfile, dpi)


def value_histogram(
    df,
    col: str,
    *,
    outfile=None,
    dpi: int = 100,
    bins: int = 40,
    xlabel: str | None = None,
    prior_range: tuple[float, float] | None = None,
):
    """Histogram of one fitted column, with the median and (optional) prior edges.

    Used for the free phase-function parameter ``B_p``, which 2.0 fits and 1.0
    held fixed: the question that histogram answers is not only "what is the
    typical value" but "did the posterior pile up against a prior edge", which
    would mean the data wanted a value the prior forbade. So ``prior_range``
    draws the bounds and the fraction within 1 % of either edge is annotated.

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    import matplotlib.pyplot as plt

    v = np.asarray(df[col], dtype=float)
    v = v[np.isfinite(v)]
    fig, ax = plt.subplots(figsize=(5, 3.4))
    if v.size:
        ax.hist(v, bins=bins, color="C0", alpha=0.85)
        med = float(np.median(v))
        ax.axvline(med, color="C3", lw=1.2, ls="--", label=f"median = {med:.4f}")
    title = f"n={v.size}"
    if prior_range and v.size:
        lo, hi = float(prior_range[0]), float(prior_range[1])
        for edge in (lo, hi):
            ax.axvline(edge, color="k", lw=1, ls=":")
        span = hi - lo
        pinned = int(
            np.count_nonzero((v <= lo + 0.01 * span) | (v >= hi - 0.01 * span))
        )
        ax.plot([], [], "k:", label=f"prior [{lo:g}, {hi:g}]")
        title += f"  at a prior edge: {pinned} ({pinned / v.size * 100:.0f} %)"
    ax.set_xlabel(xlabel or col)
    ax.set_ylabel("matchups")
    ax.set_title(title, fontsize=9)
    if v.size:
        ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
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
