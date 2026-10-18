"""Population figures (Stage 6).

Across-matchup views: the satellite-vs-in-situ ``b_bp`` log-log scatter (with
1:1 and median-ratio offset lines) as plain dots (:func:`comparison_scatter`)
or as a density-plus-dots panel (:func:`density_scatter`, what the published
Comparisons page uses at ~10⁴ matchups), the BING-vs-NASA-L2-IOP comparison
(the same plot on two satellite columns), two maps of the satellite/float
log-ratio (per matchup, :func:`matchup_map`, and per HEALPix cell,
:func:`healpix_map`), and a one-column histogram (used for the free ``B_p``).
Matplotlib/NumPy on a gathered :class:`pandas.DataFrame` (see
:mod:`pab.metrics.compare`); the maps use cartopy when it is importable and
fall back to plain lon/lat axes when it is not.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from pab.metrics.compare import log_comparison

_log = logging.getLogger("pab.plotting")

SIZE_BUDGET = 100 * 1024

#: PNG budget for the two maps. 16 k projected dots (or a few hundred
#: projected polygons) over a land background cost more than a scatter panel,
#: so the maps get their own, larger, budget.
MAP_SIZE_BUDGET = 250 * 1024

#: :func:`density_scatter` draws a histogram cell as a filled cell only when at
#: least this many matchups fall in it; sparser matchups are drawn as dots. The
#: captions quote it, so it lives here rather than only in the signature.
DENSITY_MIN_COUNT = 5

#: :func:`healpix_map` draws a cell only when it holds at least this many
#: matchups (Q&A/v2 F5). The same number as :data:`DENSITY_MIN_COUNT` today,
#: but a separate knob: one is a histogram cell, the other a patch of ocean.
HEALPIX_MIN_COUNT = 5

#: The maps' fixed symmetric colour limit on ``log10(satellite / float)``
#: (Q&A/v2 Edits 5 = B): ±0.5 dex, i.e. a factor of ≈ 3 either way. Fixed
#: rather than data-driven, so the 1.0-vs-2.0 maps and future runs read on
#: one scale; matchups at or beyond it saturate to the end colours and the
#: captions count them (:func:`log_ratio_saturated`).
LOG_RATIO_VMAX = 0.5

#: The map projection the report uses: ``"robinson"`` (cartopy) or ``None``
#: (plain lon/lat axes, no cartopy, no Natural Earth download). The map
#: functions read it at call time when ``projection="default"``, so a test
#: session can set it to ``None`` once and no map it builds touches the
#: network.
MAP_PROJECTION: str | None = "robinson"

#: The ``log10(satellite / float)`` colour map and its label, shared by both
#: maps so they read on one scale.
_RATIO_CMAP = "RdBu_r"
_RATIO_LABEL = "log10(satellite / float b_bp)"


def _clipped_range(values, clip_percentile) -> tuple[float, float]:
    """The ``(lo, hi)`` axis range for a pooled set of finite positive values.

    The central ``clip_percentile`` of the data (e.g. ``99`` → 0.5th–99.5th
    percentile), padded by × 0.7 below and × 1.4 above; without a clip the
    same padding around the extremes. One rule, shared by
    :func:`comparison_scatter`, :func:`density_scatter` and
    :func:`offscale_count`, so the figure and its caption cannot disagree.
    """
    values = np.asarray(values, dtype=float)
    if clip_percentile:
        edge = (100.0 - float(clip_percentile)) / 2.0
        lo = float(np.percentile(values, edge))
        hi = float(np.percentile(values, 100.0 - edge))
    else:
        lo = float(values.min())
        hi = float(values.max())
    return lo * 0.7, hi * 1.4


def _finite_positive(df, sat_col: str, insitu_col: str):
    """The paired arrays and the mask of finite, strictly-positive pairs."""
    sat = np.asarray(df[sat_col], dtype=float)
    insitu = np.asarray(df[insitu_col], dtype=float)
    ok = np.isfinite(sat) & np.isfinite(insitu) & (sat > 0) & (insitu > 0)
    return sat, insitu, ok


def offscale_count(
    df, sat_col: str, insitu_col: str, *, clip_percentile: float | None = 99.0
) -> int:
    """How many finite positive pairs fall outside the clipped axis range.

    The number :func:`density_scatter` prints as ``[N off-scale]``, exposed
    so a caption can state it from the same rule (:func:`_clipped_range`).
    """
    sat, insitu, ok = _finite_positive(df, sat_col, insitu_col)
    if not ok.any():
        return 0
    lo, hi = _clipped_range(np.concatenate([insitu[ok], sat[ok]]), clip_percentile)
    return int(
        np.count_nonzero(
            (insitu[ok] < lo) | (insitu[ok] > hi) | (sat[ok] < lo) | (sat[ok] > hi)
        )
    )


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

    sat, insitu, ok = _finite_positive(df, sat_col, insitu_col)
    stats = log_comparison(sat, insitu)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.loglog(insitu[ok], sat[ok], "o", ms=5, color="C0", alpha=0.8)
    offscale = 0
    if ok.any():
        lo, hi = _clipped_range(np.concatenate([insitu[ok], sat[ok]]), clip_percentile)
        if clip_percentile:
            offscale = int(
                np.count_nonzero(
                    (insitu[ok] < lo) | (insitu[ok] > hi)
                    | (sat[ok] < lo) | (sat[ok] > hi)
                )
            )
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


def density_scatter(
    df,
    sat_col: str,
    insitu_col: str,
    *,
    label: str = "b_bp",
    unit: str = "m$^{-1}$",
    xlabel: str | None = None,
    ylabel: str | None = None,
    cmap: str = "Blues",
    bins: int = 50,
    min_count: int = DENSITY_MIN_COUNT,
    clip_percentile: float | None = 99.0,
    outfile=None,
    dpi: int = 100,
):
    """Log-log density of ``sat_col`` vs ``insitu_col``: filled cells where
    the data are dense, individual dots where they are sparse.

    The all-dots :func:`comparison_scatter` fails at ~10⁴ matchups twice over:
    the dots over-plot into one blob, and a handful of non-physical retrievals
    (``b_bp`` up to 10⁵ m⁻¹) set the axes so the real population is a corner.
    So: the axes span the central ``clip_percentile`` of the pooled values
    (the :func:`comparison_scatter` rule, padded × 0.7 / × 1.4), a
    ``bins × bins`` :func:`numpy.histogram2d` of the log10 values is drawn as
    a ``pcolormesh`` wherever a cell holds **≥ ``min_count``** matchups (a
    log-count colorbar, "matchups per cell"), and the matchups in sparser
    cells are drawn one by one as small dots in a dark shade of the same hue.
    The off-scale count goes in the title as ``[N off-scale]``.

    The title statistics come from :func:`~pab.metrics.compare.log_comparison`
    on **all** finite positive pairs -- the off-scale matchups are clipped
    from the axes, not from the numbers (Q&A/v2 Q6): a failed retrieval is
    reported, not hidden. :func:`offscale_count` gives the same ``N`` to a
    caption.

    Args:
        label, unit: Used for the default axis labels
            (``"in-situ {label} [{unit}]"`` / ``"satellite {label} [{unit}]"``).
        xlabel, ylabel: Full axis-label overrides for pairings that are not
            satellite-vs-in-situ (BING vs NASA GIOP, 2.0 vs 1.0).
        cmap: A sequential Matplotlib colormap name (``Blues``, ``Greens``,
            ``Purples``); the dots take ``cmap(0.75)``.
        bins: Cells per axis over the plotted range.
        min_count: Matchups per cell at which a cell is filled rather than
            its matchups drawn as dots.
        clip_percentile: Central percentile range that sets the axes
            (``None`` → the data extremes, nothing off-scale).

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, LogNorm
    from matplotlib.patches import Patch

    sat, insitu, ok = _finite_positive(df, sat_col, insitu_col)
    stats = log_comparison(sat, insitu)
    full = plt.get_cmap(cmap)
    dot_color = full(0.75)
    # The sequential maps start at near-white, so a cell holding exactly
    # `min_count` matchups vanishes into the background and the panel's edge
    # reads as dots only. Start the mesh colours at a visible tint instead.
    cm = LinearSegmentedColormap.from_list(
        f"{cmap}_dense", full(np.linspace(0.2, 1.0, 256))
    )

    fig, ax = plt.subplots(figsize=(5.6, 5))
    offscale = 0
    handles = []
    if ok.any():
        x, y = insitu[ok], sat[ok]
        lo, hi = _clipped_range(np.concatenate([x, y]), clip_percentile)
        inside = (x >= lo) & (x <= hi) & (y >= lo) & (y <= hi)
        offscale = int(np.count_nonzero(~inside))
        lx, ly = np.log10(x[inside]), np.log10(y[inside])
        edges = np.linspace(np.log10(lo), np.log10(hi), int(bins) + 1)
        counts, _, _ = np.histogram2d(lx, ly, bins=[edges, edges])
        dense = counts >= min_count
        # The cell of every in-range matchup (clipped so a value sitting on
        # `hi` lands in the last cell, as `histogram2d` puts it).
        ix = np.clip(np.searchsorted(edges, lx, side="right") - 1, 0, bins - 1)
        iy = np.clip(np.searchsorted(edges, ly, side="right") - 1, 0, bins - 1)
        sparse = ~dense[ix, iy]
        if dense.any():
            # `histogram2d` is (x, y); `pcolormesh` wants (rows=y, cols=x).
            mesh = ax.pcolormesh(
                10.0**edges,
                10.0**edges,
                np.ma.masked_where(~dense, counts).T,
                cmap=cm,
                norm=LogNorm(vmin=min_count, vmax=float(counts.max())),
                rasterized=True,
            )
            fig.colorbar(mesh, ax=ax, label="matchups per cell", pad=0.02)
            handles.append(
                Patch(color=cm(0.5), label=f"cells with ≥ {min_count} matchups")
            )
        if sparse.any():
            (dots,) = ax.plot(
                x[inside][sparse],
                y[inside][sparse],
                "o",
                ms=2.5,
                mec="none",
                color=dot_color,
                alpha=0.6,
                rasterized=True,
                label=f"matchups in cells with < {min_count}",
            )
            handles.append(dots)
        line = np.array([lo, hi])
        handles.append(ax.plot(line, line, "k-", lw=1, label="1:1")[0])
        if np.isfinite(stats["median_ratio"]):
            handles.append(
                ax.plot(
                    line,
                    stats["median_ratio"] * line,
                    "C3--",
                    lw=1,
                    label=f"median ratio = {stats['median_ratio']:.2f}",
                )[0]
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
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
    if handles:
        ax.legend(handles=handles, fontsize=8, loc="upper left")
    # Decade gridlines only. The minor log grid shows through the light cells
    # as clutter and, measured on the real Chl 2.0-vs-1.0 panel, costs 25 KB
    # of PNG (112 KB -> 87 KB) -- the difference between over and under
    # `SIZE_BUDGET` at ~10⁴ matchups.
    ax.grid(alpha=0.3)
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


# -- maps -------------------------------------------------------------------


def log_ratio(df, sat_col: str = "bbp_bing", insitu_col: str = "bbp_argo"):
    """``log10(sat / insitu)`` per row; NaN where either value is missing or ≤ 0."""
    sat, insitu, ok = _finite_positive(df, sat_col, insitu_col)
    out = np.full(sat.shape, np.nan)
    out[ok] = np.log10(sat[ok] / insitu[ok])
    return out


def saturated_count(values, vmax: float = LOG_RATIO_VMAX) -> int:
    """How many finite ``values`` lie at or beyond ``±vmax`` -- the ones a
    colour scale clipped there shows in its end colours."""
    values = np.asarray(values, dtype=float)
    return int(np.count_nonzero(np.abs(values[np.isfinite(values)]) >= vmax))


def log_ratio_saturated(
    df,
    sat_col: str = "bbp_bing",
    insitu_col: str = "bbp_argo",
    *,
    vmax: float = LOG_RATIO_VMAX,
) -> tuple[int, int]:
    """``(saturated, n)``: the matchups whose ``log10(sat / insitu)`` is at or
    beyond ``±vmax`` -- drawn in the end colours of :func:`matchup_map` --
    and the number with a finite ratio at all. For the captions (Q&A/v2
    Edits 5), which quote the fixed clip and the fraction it saturates.
    """
    values = log_ratio(df, sat_col, insitu_col)
    n = int(np.isfinite(values).sum())
    return saturated_count(values, vmax), n


def _plural(n: int, noun: str) -> str:
    return f"{n:,} {noun}{'' if n == 1 else 's'}"


def _saturated_phrase(values, vmax: float) -> str:
    """``"1,900 (12.3 %) at or beyond"`` for the map titles."""
    values = np.asarray(values, dtype=float)
    n = int(np.isfinite(values).sum())
    sat = saturated_count(values, vmax)
    pct = f" ({100.0 * sat / n:.1f} %)" if n else ""
    return f"{sat:,}{pct} at or beyond"


def _map_axes(projection, figsize=(7.0, 4.0)):
    """A figure and axes for a global map, with the fallback chain.

    ``projection="robinson"`` → cartopy ``Robinson`` axes with Natural Earth
    land (light grey) and coastlines; ``None`` → plain lon/lat axes that need
    neither cartopy nor the network. The fallbacks, in order: cartopy not
    importable → plain axes with a warning; cartopy importable but the
    Natural Earth shapefiles neither cached nor downloadable → Robinson axes
    without land or coast, with a warning. The shapefiles are fetched
    *eagerly* (``shapereader.natural_earth``) rather than left to cartopy's
    lazy draw-time download, so a failed download is a warning here and not
    an exception out of ``savefig``.

    Returns:
        ``(fig, ax, kw)`` where ``kw`` is the keyword dict to pass to every
        lon/lat drawing call (``{"transform": PlateCarree()}`` on cartopy
        axes, empty on plain ones).
    """
    import matplotlib.pyplot as plt

    if projection == "default":
        projection = MAP_PROJECTION
    if projection not in (None, "robinson"):
        raise ValueError(f"unknown map projection {projection!r}")
    fig = plt.figure(figsize=figsize)
    if projection is not None:
        try:
            import cartopy.crs as ccrs
            import cartopy.feature as cfeature
            from cartopy.io import shapereader
        except ImportError:
            _log.warning(
                "cartopy is not importable; the map is drawn on plain lon/lat axes"
            )
            projection = None
    if projection is None:
        ax = fig.add_subplot(111)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_aspect("equal")
        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")
        ax.grid(alpha=0.3)
        return fig, ax, {}
    ax = fig.add_subplot(111, projection=ccrs.Robinson())
    ax.set_global()
    try:
        # cartopy's features download on first draw; resolve the two files
        # now so "no network and no cache" is caught here, once.
        for name in ("land", "coastline"):
            shapereader.natural_earth(resolution="110m", category="physical", name=name)
    except Exception as exc:  # noqa: BLE001 — any download failure
        _log.warning(
            "Natural Earth coastlines unavailable (%s); map drawn without land", exc
        )
    else:
        ax.add_feature(
            cfeature.LAND.with_scale("110m"),
            facecolor="0.85",
            edgecolor="none",
            zorder=0,
        )
        ax.coastlines(resolution="110m", linewidth=0.4, color="0.35", zorder=1)
    ax.gridlines(linewidth=0.3, color="0.6", alpha=0.6, zorder=1)
    return fig, ax, {"transform": ccrs.PlateCarree()}


def _ratio_colorbar(fig, mappable, ax, label):
    fig.colorbar(
        mappable, ax=ax, label=label, extend="both", shrink=0.8, pad=0.02
    )


def matchup_map(
    df,
    *,
    sat_col: str = "bbp_bing",
    insitu_col: str = "bbp_argo",
    color_col: str | None = None,
    vmax: float = LOG_RATIO_VMAX,
    projection: str | None = "default",
    outfile=None,
    dpi: int = 100,
):
    """The matchup positions as dots coloured by ``log10(sat / float)``.

    A Robinson map (cartopy; see :func:`_map_axes` for the fallbacks) with
    light-grey land, one dot per matchup (marker size 3, alpha 0.6) on a
    red-blue scale **symmetric about 0** and clipped at the fixed ``vmax``
    (:data:`LOG_RATIO_VMAX`, ±0.5 dex; Q&A/v2 Q8, Edits 5), the same scale
    as :func:`healpix_map`; matchups at or beyond the clip take the end
    colours and the title counts them. The ratio is computed here from the
    two columns -- the caller does not pass a ratio column -- so a runaway
    retrieval cannot reach the colour scale through a caller. Matchups with
    a position but no finite ratio (no float value) are drawn as small grey
    dots underneath.

    Args:
        color_col: Colour by this column of ready-made values instead of the
            log-ratio of ``sat_col``/``insitu_col`` (the colorbar is then
            labelled with the column name); the same symmetric scale.
        vmax: The symmetric colour limit, in dex.
        projection: ``"robinson"``, ``None`` (plain lon/lat axes; never
            touches cartopy or the network -- what the tests use) or
            ``"default"`` → :data:`MAP_PROJECTION`.

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    from matplotlib.colors import Normalize

    lon = np.asarray(df["longitude"], dtype=float)
    lat = np.asarray(df["latitude"], dtype=float)
    if color_col:
        values = np.asarray(df[color_col], dtype=float)
        label = color_col
    else:
        values = log_ratio(df, sat_col, insitu_col)
        label = _RATIO_LABEL
    positioned = np.isfinite(lon) & np.isfinite(lat)
    coloured = positioned & np.isfinite(values)
    grey = positioned & ~coloured

    fig, ax, kw = _map_axes(projection)
    if grey.any():
        ax.scatter(
            lon[grey], lat[grey], s=4, color="0.55", alpha=0.5, linewidths=0,
            rasterized=True, zorder=2, **kw,
        )
    sc = ax.scatter(
        lon[coloured],
        lat[coloured],
        c=values[coloured],
        cmap=_RATIO_CMAP,
        norm=Normalize(-vmax, vmax),
        s=9,  # marker size 3 (area = 3²)
        alpha=0.6,
        linewidths=0,
        rasterized=True,
        zorder=3,
        **kw,
    )
    _ratio_colorbar(fig, sc, ax, label)
    n = int(coloured.sum())
    title = (
        f"{n:,} matchups; colour clipped at ±{vmax:g} dex "
        f"({_saturated_phrase(values[coloured], vmax)})"
    )
    if grey.any():
        title += f"; {int(grey.sum()):,} without a ratio in grey"
    ax.set_title(title, fontsize=9)
    return _finish(fig, outfile, dpi)


def healpix_medians(
    df,
    sat_col: str = "bbp_bing",
    insitu_col: str = "bbp_argo",
    *,
    cell_size_deg: float = 5.0,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
):
    """Per-HEALPix-cell count and median ``log10(sat / insitu)``.

    Cells via :func:`pab.report.aggregate.nside_for_cell_size` /
    :func:`~pab.report.aggregate.assign_healpix`; only matchups with a
    position and a finite positive pair are binned. Every occupied cell is
    returned -- :func:`healpix_map` applies its ``min_count`` -- so a caption
    can say how many cells were drawn and how many left out.

    Returns:
        A :class:`pandas.DataFrame` with ``hpix``, ``nside``, ``n``,
        ``median_log_ratio``, one row per occupied cell.
    """
    import pandas as pd

    from pab.report.aggregate import assign_healpix, nside_for_cell_size

    nside = nside_for_cell_size(cell_size_deg)
    values = log_ratio(df, sat_col, insitu_col)
    lat = np.asarray(df[lat_col], dtype=float)
    lon = np.asarray(df[lon_col], dtype=float)
    ok = np.isfinite(values) & np.isfinite(lat) & np.isfinite(lon)
    if not ok.any():
        return pd.DataFrame(
            {"hpix": [], "nside": [], "n": [], "median_log_ratio": []}
        ).astype({"hpix": int, "nside": int, "n": int})
    cells = assign_healpix(lat[ok], lon[ok], nside)
    out = (
        pd.DataFrame({"hpix": cells, "log_ratio": values[ok]})
        .groupby("hpix")["log_ratio"]
        .agg(n="size", median_log_ratio="median")
        .reset_index()
    )
    out.insert(1, "nside", int(nside))
    return out


def healpix_cell_deg(nside: int) -> float:
    """The approximate HEALPix cell width in degrees (``healpy.nside2resol``)."""
    import healpy

    return float(healpy.nside2resol(int(nside), arcmin=True) / 60.0)


def _cell_outline(nside: int, pix: int):
    """The lon/lat outline of one HEALPix cell, longitudes in ``[0, 360)``.

    ``healpy.boundaries`` returns unit vectors (its ``lonlat`` keyword only
    exists in newer releases), converted with ``vec2ang``. A polar cap cell
    has the pole itself as a vertex, whose longitude comes back as 0
    (``atan2(0, 0)``) whatever the cell; it is replaced by the circular mean
    of its two neighbours so the outline does not run along the pole line.
    """
    import healpy

    vec = healpy.boundaries(nside, int(pix), step=4)
    lon, lat = healpy.vec2ang(vec.T, lonlat=True)
    lon = np.mod(lon, 360.0)
    for i in np.flatnonzero(np.abs(lat) > 89.999):
        a, b = np.radians(lon[i - 1]), np.radians(lon[(i + 1) % lon.size])
        mean = np.degrees(
            np.arctan2(np.sin(a) + np.sin(b), np.cos(a) + np.cos(b))
        )
        lon[i] = np.mod(mean, 360.0)
    return lon, lat


def _clip_lon(lon, lat, edge: float, keep_below: bool):
    """Sutherland-Hodgman clip of a lon/lat polygon against one meridian."""
    out = []
    n = lon.size
    for i in range(n):
        x1, y1 = lon[i], lat[i]
        x2, y2 = lon[(i + 1) % n], lat[(i + 1) % n]
        in1 = x1 <= edge if keep_below else x1 >= edge
        in2 = x2 <= edge if keep_below else x2 >= edge
        if in1:
            out.append((x1, y1))
        if in1 != in2:
            t = (edge - x1) / (x2 - x1)
            out.append((edge, y1 + t * (y2 - y1)))
    arr = np.array(out, dtype=float)
    return arr[:, 0], arr[:, 1]


def _dateline_pieces(lon, lat):
    """A cell outline (lon in ``[0, 360)``) as one or two polygons in
    ``[-180, 180]``.

    A cell that straddles the dateline is **split** at 180° into a western
    and an eastern piece (both then lie inside the plain-axes range, and
    cartopy's ``PlateCarree`` → ``Robinson`` projection no longer sees a
    polygon that appears to go the long way round the globe -- the "smear"
    across the whole map). A cell that straddles 0° is compact in
    ``[-180, 180]`` once its eastern vertices are shifted by −360.

    A cell whose *edge* lies on the dateline (a vertex at 180° to within
    ``eps``) is not a straddler: clipping it would leave a zero-width sliver
    at 180°, which cartopy projects as the **whole globe** (a degenerate
    ring reads as an inside-out polygon) -- the first render of the real map
    was a pale-blue planet for exactly that reason.

    Returns:
        ``(pieces, split)``: a list of ``(lon, lat)`` arrays and whether the
        cell was split.
    """
    eps = 1e-6
    if lon.max() - lon.min() > 180.0:  # straddles 0°, not the dateline
        pieces, split = [(np.where(lon > 180.0, lon - 360.0, lon), lat)], False
    elif lon.min() < 180.0 - eps and lon.max() > 180.0 + eps:  # straddles 180°
        west = _clip_lon(lon, lat, 180.0, keep_below=True)
        east_lon, east_lat = _clip_lon(lon, lat, 180.0, keep_below=False)
        pieces, split = [west, (east_lon - 360.0, east_lat)], True
    elif lon.min() >= 180.0 - eps:  # wholly on or east of the dateline
        pieces, split = [(lon - 360.0, lat)], False
    else:
        pieces, split = [(lon, lat)], False
    # the shifts leave float noise (-180.00000000000003); keep every piece
    # inside the plain-axes range
    return [(np.clip(plon, -180.0, 180.0), plat) for plon, plat in pieces], split


def healpix_map(
    df,
    *,
    sat_col: str = "bbp_bing",
    insitu_col: str = "bbp_argo",
    cell_size_deg: float = 5.0,
    min_count: int = HEALPIX_MIN_COUNT,
    vmax: float = LOG_RATIO_VMAX,
    projection: str | None = "default",
    outfile=None,
    dpi: int = 100,
):
    """Median ``log10(sat / float)`` per HEALPix cell, on the same map and
    colour scale as :func:`matchup_map`.

    Where the dot map over-plots 16 k matchups, this draws one patch per
    cell: the cells from :func:`healpix_medians` (``cell_size_deg`` → nside
    via ``remote_sensing``), **only those holding ≥ ``min_count`` matchups**
    (Q&A/v2 F5), as polygons from ``healpy.boundaries`` (16 vertices each)
    through ``PlateCarree`` onto the Robinson/land background. Cells that
    straddle the dateline are split in two (:func:`_dateline_pieces`; the
    number is logged). The colour scale is the fixed ``vmax``
    (:data:`LOG_RATIO_VMAX`, ±0.5 dex) shared with :func:`matchup_map`. The
    title gives the cells drawn, the matchups they hold, the sparser cells
    left out and the drawn cells whose median is at or beyond the clip
    (saturated).

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import Normalize

    cells = healpix_medians(
        df, sat_col, insitu_col, cell_size_deg=cell_size_deg
    )
    drawn = cells[cells["n"] >= min_count]
    nside = int(cells["nside"].iloc[0]) if len(cells) else 0
    verts, colours, n_split = [], [], 0
    for pix, value in zip(drawn["hpix"], drawn["median_log_ratio"], strict=True):
        pieces, split = _dateline_pieces(*_cell_outline(nside, pix))
        n_split += int(split)
        for lon, lat in pieces:
            verts.append(np.column_stack([lon, lat]))
            colours.append(value)
    if n_split:
        _log.info(
            "healpix_map: %d of %d cells straddle the dateline and were split",
            n_split,
            len(drawn),
        )

    fig, ax, kw = _map_axes(projection)
    coll = PolyCollection(
        verts,
        array=np.asarray(colours, dtype=float),
        cmap=_RATIO_CMAP,
        norm=Normalize(-vmax, vmax),
        edgecolors="none",
        rasterized=True,
        zorder=2,
        **kw,
    )
    ax.add_collection(coll)
    _ratio_colorbar(fig, coll, ax, f"median {_RATIO_LABEL}")
    res = healpix_cell_deg(nside) if nside else float("nan")
    ax.set_title(
        f"{len(drawn)} HEALPix cells (nside {nside}, ≈{res:.1f}°) with "
        f"≥ {min_count} matchups, holding {int(drawn['n'].sum()):,} matchups\n"
        f"{len(cells) - len(drawn)} sparser cells not drawn; "
        f"colour clipped at ±{vmax:g} dex "
        f"({_plural(saturated_count(drawn['median_log_ratio'], vmax), 'cell')} saturated)",
        fontsize=9,
    )
    return _finish(fig, outfile, dpi)


def _finish(fig, outfile, dpi):
    import matplotlib.pyplot as plt

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return outfile
    return fig
