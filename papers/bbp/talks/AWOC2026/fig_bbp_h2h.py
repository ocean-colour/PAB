"""
PACE vs BGC-Argo b_bp(700) head-to-head figures for the AWOC 2026 talk
(``papers/bbp/prompts/talks/aw2026_bbp_argo_pace.md``, Prompts/Head-to-head).

Figures (one Google slide each; the slide carries the title, so each figure
is 4.6 in tall -- a square log-log axis plus a colour bar, ~6.2 in wide,
legend (upper left) and statistics (lower right) inside the axes; prompt 4):
    1  fig_bbp_h2h_raw.png -- log-log 2D histogram of PACE (BING v2.1) vs
       Argo mixed-layer b_bp(700), 0.1-dex cells drawn only where they hold
       >= 10 matchups, coloured by count (Purples, log scale); 1:1 line.
    2  fig_bbp_h2h_cells_dots.png -- the same, plus the matchups in the
       sparser cells as grey dots.
    3  fig_bbp_h2h_dots.png -- every matchup as a dot, coloured by the
       BING (PACE) Chl, log scale (prompt 4).

Choices (Q&A/Head-to-head):
    * matchups: dx < 10 km, dt < 3 h, successful v2.1 BING fit (rank-1 pixel),
      b_bp > 0 on both sides; no other cuts (Q2);
    * float 5907147 (Ligurian Sea; Argo b_bp ~3e-2 at Chl 0.1, a suspect
      sensor) is masked from the figure *and* the statistics (Q9, Q10);
    * axes 1e-4 to 1e-2 m^-1 on both; matchups outside are not drawn and
      not noted (Q8, Q12), but they *are* in the statistics (Q10);
    * statistics (:func:`pab.metrics.compare.log_comparison`): N, median
      PACE/Argo, Spearman rho, log10 RMS (Q6, Q10).

The cell/dot logic follows :func:`pab.plotting.population.density_scatter`
(the paper's version), restyled for a slide: that function builds its own
5.6 x 5 in figure with the statistics in a 9-pt title, so it is mirrored
here rather than called. The Chl colour scale matches ``fig_global.py``.

Usage:
    python papers/bbp/talks/AWOC2026/fig_bbp_h2h.py 1     # cells only
    python papers/bbp/talks/AWOC2026/fig_bbp_h2h.py 2     # cells + sparse dots
    python papers/bbp/talks/AWOC2026/fig_bbp_h2h.py 3     # all dots, by PACE Chl
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import cmocean
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from pab.config import DATA_DIR
from pab.metrics.compare import log_comparison

# ── defaults ──────────────────────────────────────────────────────────────────

#: The v2.1 release database.
DEFAULT_DB = Path(DATA_DIR) / "v2" / "pab.db"

#: Output directory: next to this script.
DEFAULT_OUT_DIR = Path(__file__).resolve().parent

#: Matchup definition (doc "Context").
DX_MAX_KM = 10.0
DT_MAX_H = 3.0

#: BING release and quantities shown (Q1, prompt 4).
PAB_VERSION = "2.1"
BBP_QUANTITY = "BING_ExpBPow_bbp700"
CHL_QUANTITY = "BING_ExpBPow_chl"

#: Floats masked from the figure and the statistics (Q9): 5907147 reports
#: mixed-layer b_bp ~3e-2 m^-1 (capped at 0.05) at Chl ~0.1 mg m^-3.
MASK_WMO = (5907147,)

#: Axis limits, both axes (Q8 a), m^-1.
LIM = (1e-4, 1e-2)

#: Cell width in log10 (Q4) and the fill threshold (prompt 1).
DEX = 0.1
MIN_COUNT = 10

#: Colours (Q5): Purples for the cells (the b_bp hue of the BING-fit
#: slides), grey for the sparse dots.
CMAP = "Purples"
DOT_COLOR = "#7f7f7f"

#: PACE Chl colour scale for figure 3: log10, clipped, cmocean "algae" --
#: the same as the global-matchup map (fig_global.py), so the slides agree.
CHL_LIM = (0.01, 3.0)       # mg m^-3
CMAP_CHL = cmocean.cm.algae

RC = {
    "font.size": 14, "axes.labelsize": 16, "xtick.labelsize": 13,
    "ytick.labelsize": 13, "legend.fontsize": 12, "figure.dpi": 150,
    "savefig.dpi": 300,
}

#: Layout (inches): a square data axis, then the colour bar and its label.
#: The slide height (~4.6 in under the title) sets the axis size; the figure
#: is only as wide as the axis + colour bar (prompt 4: narrower).
FIG_H = 4.6
AX_X0, AX_Y0, AX_SIDE = 1.15, 0.72, 3.75
CB_GAP, CB_W, CB_LABEL = 0.18, 0.18, 0.95
FIG_W = AX_X0 + AX_SIDE + CB_GAP + CB_W + CB_LABEL      # ~6.2 in


# ── data ──────────────────────────────────────────────────────────────────────

def load_matchups(db=None, dx_max: float = DX_MAX_KM, dt_max: float = DT_MAX_H,
                  mask_wmo=MASK_WMO) -> pd.DataFrame:
    """PACE (BING) and Argo b_bp(700), and the BING Chl, for every matchup.

    Args:
        db: Path to ``pab.db``; default :data:`DEFAULT_DB`.
        dx_max, dt_max: The matchup definition (km, h). ``dtime_hours`` is
            stored as an absolute value.
        mask_wmo: Floats to drop.

    Returns:
        One row per matchup with a successful v2.1 BING fit on the rank-1
        pixel and b_bp > 0 on both sides: ``wmo``, ``cycle``,
        ``bbp_argo`` (de-spiked mixed-layer mean), ``bbp_pace`` (posterior
        median), both m^-1, and ``chl_pace`` (BING posterior-median Chl,
        mg m^-3).
    """
    con = sqlite3.connect(db or DEFAULT_DB)
    df = pd.read_sql(
        """SELECT p.wmo, p.cycle, mp.rank, m.matchup_id,
                  s.bbp700 AS bbp_argo, r.value AS bbp_pace,
                  rc.value AS chl_pace
           FROM matchups m
           JOIN profiles p USING (profile_id)
           JOIN mld_summary s USING (profile_id)
           JOIN fits f ON f.matchup_id = m.matchup_id
           LEFT JOIN matchup_pixels mp ON mp.pixel_id = f.pixel_id
           JOIN fit_results r ON r.fit_id = f.fit_id AND r.quantity = ?
           LEFT JOIN fit_results rc ON rc.fit_id = f.fit_id AND rc.quantity = ?
           WHERE m.distance_km < ? AND m.dtime_hours < ?
             AND f.algorithm = 'BING' AND f.pab_version = ? AND f.success = 1""",
        con, params=(BBP_QUANTITY, CHL_QUANTITY, dx_max, dt_max, PAB_VERSION),
    )
    con.close()
    # one fit per matchup: the best-ranked pixel (production fits only rank 1)
    df = (df.sort_values("rank", na_position="last", kind="stable")
            .drop_duplicates("matchup_id"))
    df = df[(df["bbp_argo"] > 0) & (df["bbp_pace"] > 0)]
    df = df[~df["wmo"].isin(mask_wmo)]
    return df.reset_index(drop=True)


def in_range(df: pd.DataFrame, lim=LIM) -> np.ndarray:
    """Boolean mask of the matchups inside ``lim`` on both axes (the drawn ones)."""
    x, y = df["bbp_argo"].to_numpy(float), df["bbp_pace"].to_numpy(float)
    return (x >= lim[0]) & (x <= lim[1]) & (y >= lim[0]) & (y <= lim[1])


# ── shared layout ─────────────────────────────────────────────────────────────

def _axes(fig):
    """The square data axis and the colour-bar axis (positions in inches)."""
    ax = fig.add_axes([AX_X0 / FIG_W, AX_Y0 / FIG_H,
                       AX_SIDE / FIG_W, AX_SIDE / FIG_H])
    cax = fig.add_axes([(AX_X0 + AX_SIDE + CB_GAP) / FIG_W, AX_Y0 / FIG_H,
                        CB_W / FIG_W, AX_SIDE / FIG_H])
    return ax, cax


def _stats_text(stats: dict) -> str:
    """The four statistics (Q6, Q10), one per line."""
    return "\n".join([
        f"N = {stats['n']:,}",
        f"PACE/Argo = {stats['median_ratio']:.2f}",
        rf"Spearman $\rho$ = {stats['spearman']:.2f}",
        f"log$_{{10}}$ RMS = {stats['log_rms']:.2f}",
    ])


def _finish(ax, df, handles, lim=LIM):
    """Log-log axes, labels, 1:1 line, statistics (lower right) and legend
    (upper left), all inside the axes (prompt 4)."""
    ax.plot(lim, lim, "k-", lw=1.5, zorder=4)                # 1:1 (Q6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal")
    ax.set_xlabel(r"Argo $b_{bp}(700)$ (m$^{-1}$)")
    ax.set_ylabel(r"PACE $b_{bp}(700)$ (m$^{-1}$)")
    ax.grid(alpha=0.3, zorder=0)                             # decades only

    # statistics on every (unmasked) matchup, on- or off-scale (Q10)
    stats = log_comparison(df["bbp_pace"].to_numpy(float),
                           df["bbp_argo"].to_numpy(float))
    # The data leave two corners nearly empty: below the 1:1 line at high
    # Argo b_bp (lower right) and above it at low Argo b_bp (upper left).
    # The stats go in the first, the legend in the second.
    ax.text(0.97, 0.03, _stats_text(stats), transform=ax.transAxes,
            ha="right", va="bottom", fontsize=12, linespacing=1.45, zorder=6)
    # (no filled box: a white fill hides the low-PACE tail beneath it)
    handles = handles + [Line2D([], [], color="k", lw=1.5, label="1:1")]
    leg = ax.legend(handles=handles, loc="upper left", frameon=True,
                    framealpha=0.75, edgecolor="none", handlelength=1.2,
                    borderaxespad=0.3)
    leg.set_zorder(6)
    return stats


# ── figures ───────────────────────────────────────────────────────────────────

def fig_bbp_h2h(df: pd.DataFrame, out=None, dots: bool = False,
                lim=LIM, dex: float = DEX, min_count: int = MIN_COUNT):
    """PACE vs Argo b_bp(700): dense cells, optionally the sparse dots.

    Args:
        df: Output of :func:`load_matchups`.
        out: Path to save the PNG; nothing is saved if ``None``.
        dots: Also draw the matchups in cells with < ``min_count`` as grey dots.
        lim: (min, max) of both axes (m^-1). Matchups outside are not drawn.
        dex: Cell width in log10.
        min_count: Matchups a cell needs to be filled.

    Returns:
        The matplotlib Figure.
    """
    inside = in_range(df, lim)
    x = df["bbp_argo"].to_numpy(float)[inside]
    y = df["bbp_pace"].to_numpy(float)[inside]

    # 2D histogram in log10 over the plotted range
    lo, hi = np.log10(lim)
    nbin = int(round((hi - lo) / dex))
    edges = np.linspace(lo, hi, nbin + 1)
    lx, ly = np.log10(x), np.log10(y)
    counts, _, _ = np.histogram2d(lx, ly, bins=[edges, edges])
    dense = counts >= min_count
    # each in-range matchup's cell (a value on `hi` goes in the last cell,
    # as histogram2d puts it) -> which matchups are in sparse cells
    ix = np.clip(np.searchsorted(edges, lx, side="right") - 1, 0, nbin - 1)
    iy = np.clip(np.searchsorted(edges, ly, side="right") - 1, 0, nbin - 1)
    sparse = ~dense[ix, iy]

    # Purples starts near white; start at a visible tint so a 10-count cell
    # does not vanish into the background (as density_scatter does)
    full = plt.get_cmap(CMAP)
    cmap = LinearSegmentedColormap.from_list("purples_dense",
                                             full(np.linspace(0.2, 1.0, 256)))

    with mpl.rc_context(RC):
        fig = plt.figure(figsize=(FIG_W, FIG_H))
        ax, cax = _axes(fig)

        mesh = ax.pcolormesh(10.0**edges, 10.0**edges,
                             np.ma.masked_where(~dense, counts).T,
                             cmap=cmap,
                             norm=LogNorm(vmin=min_count, vmax=counts.max()),
                             rasterized=True, zorder=2)
        if dots and sparse.any():
            ax.plot(x[sparse], y[sparse], "o", ms=3.0, mec="none",
                    color=DOT_COLOR, alpha=0.7, rasterized=True, zorder=3)

        cb = fig.colorbar(mesh, cax=cax)
        cb.set_label("matchups per cell")
        cb.ax.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter("%g"))
        cb.ax.yaxis.set_minor_formatter(mpl.ticker.NullFormatter())
        cb.set_ticks([t for t in (10, 20, 50, 100, 200) if t <= counts.max()])

        # legend: what the cells (and dots) are
        handles = [Patch(color=cmap(0.5), label=f"cells with ≥ {min_count}")]
        if dots:
            handles.append(Line2D([], [], ls="none", marker="o", ms=5,
                                  mec="none", color=DOT_COLOR,
                                  label=f"cells with < {min_count}"))
        _finish(ax, df, handles, lim)

    if out is not None:
        fig.savefig(out)
    return fig


def fig_bbp_h2h_chl(df: pd.DataFrame, out=None, lim=LIM, chl_lim=CHL_LIM,
                    seed: int = 1):
    """PACE vs Argo b_bp(700), every matchup a dot coloured by PACE Chl.

    Chl is the BING posterior-median Chl of the same fit, on a log10 scale
    clipped to ``chl_lim`` (the colour bar's arrows mark the clipping).
    The dots are drawn in a random (seeded) order, so neither high nor low
    Chl systematically hides the other where they overlap.

    Args:
        df: Output of :func:`load_matchups`.
        out: Path to save the PNG; nothing is saved if ``None``.
        lim: (min, max) of both axes (m^-1). Matchups outside are not drawn.
        chl_lim: (min, max) of the Chl colour scale (mg m^-3).
        seed: Seed of the drawing order.

    Returns:
        The matplotlib Figure.
    """
    d = df[in_range(df, lim)]
    d = d.sample(frac=1.0, random_state=seed)                # drawing order
    chl = d["chl_pace"].clip(*chl_lim)

    with mpl.rc_context(RC):
        fig = plt.figure(figsize=(FIG_W, FIG_H))
        ax, cax = _axes(fig)

        sc = ax.scatter(d["bbp_argo"], d["bbp_pace"], c=chl, cmap=CMAP_CHL,
                        norm=LogNorm(*chl_lim), s=9, linewidths=0.2,
                        edgecolors="#33333355", rasterized=True, zorder=3)

        cb = fig.colorbar(sc, cax=cax, extend="both")
        cb.set_label(r"PACE Chl (mg m$^{-3}$)")
        cb.ax.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter("%g"))

        handles = [Line2D([], [], ls="none", marker="o", ms=5, mec="none",
                          color=CMAP_CHL(0.6), label="matchup")]
        _finish(ax, df, handles, lim)

    if out is not None:
        fig.savefig(out, dpi=300)
    return fig


# ── CLI ───────────────────────────────────────────────────────────────────────

#: Figure flags for :func:`main`.
FIGURES = {
    1: "cells only (fig_bbp_h2h_raw.png)",
    2: "cells + sparse dots (fig_bbp_h2h_cells_dots.png)",
    3: "all matchups as dots, coloured by PACE Chl (fig_bbp_h2h_dots.png)",
}


def main(flg: int):
    """Make figure ``flg`` (see :data:`FIGURES`) in :data:`DEFAULT_OUT_DIR`."""
    if flg not in FIGURES:
        raise ValueError(f"Unknown figure {flg}; choose from {FIGURES}")

    df = load_matchups()
    if flg == 1:
        out = DEFAULT_OUT_DIR / "fig_bbp_h2h_raw.png"
        fig = fig_bbp_h2h(df, out=out, dots=False)
    elif flg == 2:
        out = DEFAULT_OUT_DIR / "fig_bbp_h2h_cells_dots.png"
        fig = fig_bbp_h2h(df, out=out, dots=True)
    elif flg == 3:
        out = DEFAULT_OUT_DIR / "fig_bbp_h2h_dots.png"
        fig = fig_bbp_h2h_chl(df, out=out)
    plt.close(fig)
    print(f"✓ {out}  (N = {len(df):,}, {df['wmo'].nunique()} floats, "
          f"{in_range(df).sum():,} on-scale; masked {MASK_WMO})")


if __name__ == "__main__":
    # python fig_bbp_h2h.py <n>; no argument means figure 1
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
