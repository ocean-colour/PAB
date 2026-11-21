"""
Argo figures for the AWOC 2026 talk (``papers/bbp/prompts/talks/aw2026_argo.md``).

Figures:
    fig_argo_<wmo>_<cycle>.png -- (a) the BGC-Argo b_bp(700) profile of one
                                  float cycle, after the Argo panel of the
                                  Bokeh viewer (``pab/viz/bokeh_argo_pace.py``)
                                  without the PACE/GIOP estimates;
                                  (b) a zoomed map of the float's position
                                  with the other matchups in view.

The stored MLD and mixed-layer mean come from the live v2.1 PAB database
(``$PAB_DATA_DIR/v2/pab.db``); the samples are re-fetched from the GDAC with
argopy exactly as the ingest did (:func:`pab.viz.argo.fetch_argo_profile`),
so this needs network access. Needs cartopy (ocean14).

Usage:
    python papers/bbp/talks/AWOC2026/fig_argo.py 1     # profile figure, module defaults

Change the profile, depth or output by editing ``DEFAULT_WMO`` /
``DEFAULT_CYCLE`` / ``DEFAULT_OUT_DIR``, or by calling
``fig_argo_profile(wmo, cycle, out=..., pmax=...)`` from Python.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pab.config import DATA_DIR
from pab.viz import argo as vargo
from pab.viz import data as vdata
from pab.viz.bokeh_argo_pace import (ARGO_COLOR, DROP_COLOR, NO_MLD_DEPTH,
                                     RAW_COLOR, load_selection)

# ── defaults ──────────────────────────────────────────────────────────────────

#: The v2.1 release database.
DEFAULT_DB = Path(DATA_DIR) / "v2" / "pab.db"

#: Output directory: next to this script.
DEFAULT_OUT_DIR = Path(__file__).resolve().parent


#: Matchup definition (doc "Context"), for the other matchups on the map.
DX_MAX_KM = 10.0
DT_MAX_H = 3.0

#: Shallowest bottom of the profile panel (Q2, option c): max(2 MLD, this).
PMAX_MIN = 100.0

#: Map extent (Q4): lon_min, lon_max, lat_min, lat_max -- all of Honshu.
MAP_EXTENT = (128.0, 148.0, 28.0, 46.0)

#: Minimum distance (deg) kept between the float and the map edge; the
#: extent grows to honour it.
MAP_MARGIN = 2.0

#: Float marker on the map.
FLOAT_COLOR = "#d62728"

RC = {
    "font.size": 11, "axes.labelsize": 12, "axes.titlesize": 12,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 9,
    "figure.dpi": 150, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
}


# ── data ──────────────────────────────────────────────────────────────────────

def load_profile(wmo: int, cycle: int, db=None):
    """Stored matchup values and re-fetched samples for ``(wmo, cycle)``.

    Returns:
        ``(sel, layers)``: the :class:`pab.viz.bokeh_argo_pace.Selection`
        (``sel.matchup`` holds the stored MLD, ``bbp700``, ``bbp700_std``,
        time, dx, dt) and the :class:`pab.viz.argo.BbpLayers` of the fetched
        profile (raw, de-spiked and IQR-rejected samples), split at the
        stored MLD as the viewer does.
    """
    store = vdata.open_store(db or DEFAULT_DB)
    sel = load_selection(store, wmo, cycle)
    if sel.matchup is None:
        raise ValueError(f"No matchup for wmo {wmo}, cycle {cycle} in the DB")
    prof = vargo.fetch_argo_profile(int(wmo), int(cycle))
    layers = vargo.bbp_layers(prof.pres, prof.bbp, sel.mld, prof.bbp_qc)
    return sel, layers


def load_matchups_in_box(db=None, extent=MAP_EXTENT, dx_max: float = DX_MAX_KM,
                         dt_max: float = DT_MAX_H) -> pd.DataFrame:
    """Positions of every matchup (dx < ``dx_max`` km, dt < ``dt_max`` h)
    inside ``extent`` = (lon_min, lon_max, lat_min, lat_max)."""
    lon0, lon1, lat0, lat1 = extent
    con = sqlite3.connect(db or DEFAULT_DB)
    df = pd.read_sql(
        """SELECT p.wmo, p.cycle, p.latitude, p.longitude
           FROM matchups m JOIN profiles p USING (profile_id)
           WHERE m.distance_km < ? AND m.dtime_hours < ?
             AND p.longitude BETWEEN ? AND ? AND p.latitude BETWEEN ? AND ?""",
        con, params=(dx_max, dt_max, lon0, lon1, lat0, lat1),
    )
    con.close()
    return df


# ── panels ────────────────────────────────────────────────────────────────────

def _profile_panel(ax, sel, layers, pmax: float):
    """(a) b_bp(700) vs pressure, after the Bokeh viewer's Argo panel (Q3):
    raw samples, de-spiked line, IQR-rejected samples (if any), the stored
    ML mean ± std down to the MLD, and the MLD."""
    m = sel.matchup
    mld = sel.mld
    top = sel.ml_span                         # ML values drawn down to the MLD

    # stored ML mean ± std (the DB value, as in the viewer)
    mean, std = m.get("bbp700"), m.get("bbp700_std")
    if mean is not None and np.isfinite(mean):
        if std is not None and np.isfinite(std):
            ax.fill_betweenx([0, top], mean - std, mean + std, color=ARGO_COLOR,
                             alpha=0.18, lw=0, zorder=1)
        ax.plot([mean, mean], [0, top], color=ARGO_COLOR, lw=3, zorder=2,
                label="Argo ML mean ± std")

    # samples
    ok = np.isfinite(layers.raw) & np.isfinite(layers.pres)
    ax.scatter(layers.raw[ok], layers.pres[ok], s=14, color=RAW_COLOR,
               alpha=0.8, linewidths=0, zorder=3, label="raw samples")
    okd = np.isfinite(layers.despiked) & np.isfinite(layers.pres)
    ax.plot(layers.despiked[okd], layers.pres[okd], color="black", lw=1.2,
            zorder=4, label="de-spiked (3-pt median)")
    if layers.dropped.any():
        d = layers.dropped
        ax.scatter(layers.despiked[d], layers.pres[d], s=30, facecolors="none",
                   edgecolors=DROP_COLOR, linewidths=1.5, zorder=5,
                   label="IQR-rejected (in ML)")

    # MLD
    if np.isfinite(mld):
        ax.axhline(mld, color="black", ls="--", lw=1.2, zorder=2)
        ax.text(0.98, mld, "MLD", transform=ax.get_yaxis_transform(),
                ha="right", va="bottom", fontsize=10)

    # x range: the samples inside the window plus the band (viewer's rule)
    inwin = ok & (layers.pres <= pmax)
    vals = list(layers.raw[inwin])
    if mean is not None and np.isfinite(mean):
        vals += [mean - (std or 0), mean + (std or 0)]
    vals = np.asarray([v for v in vals if np.isfinite(v)])
    if vals.size:
        lo, hi = vals.min(), vals.max()
        pad = 0.08 * (hi - lo) if hi > lo else 0.1 * abs(hi)
        ax.set_xlim(max(lo - pad, 0.0) if lo >= 0 else lo - pad, hi + pad)

    ax.set_ylim(pmax, 0)                      # pressure increases downward
    ax.set_xlabel(r"$b_{bp}(700)$ (m$^{-1}$)")
    ax.set_ylabel("pressure (dbar)")
    fmt = mpl.ticker.ScalarFormatter(useMathText=True)
    fmt.set_powerlimits((-2, 2))
    ax.xaxis.set_major_formatter(fmt)
    ax.grid(True, color="#e4e3df", lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("(a) BGC-Argo $b_{bp}(700)$", loc="left")


def _map_panel(ax, sel, others: pd.DataFrame, extent=MAP_EXTENT):
    """(b) Zoomed map: land, coastline, graticule labels, the other matchups
    as small dots and the float as a star labelled with wmo/cycle and date."""
    m = sel.matchup
    lon, lat = float(m["longitude"]), float(m["latitude"])
    extent = _extent_with_float(extent, lon, lat)
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#d9d9d9", zorder=0)
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#f0f4f8", zorder=0)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.6, zorder=1)
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="#aaaaaa",
                      alpha=0.6, linestyle="--")
    gl.top_labels = gl.right_labels = False
    gl.xlocator = mpl.ticker.MultipleLocator(5)    # every 5°: no crowding
    gl.ylocator = mpl.ticker.MultipleLocator(5)

    # other matchups (Q4), excluding this profile
    o = others[~((others["wmo"] == sel.wmo) & (others["cycle"] == sel.cycle))]
    ax.scatter(o["longitude"], o["latitude"], s=12, color="#555555",
               linewidths=0, alpha=0.8, transform=ccrs.PlateCarree(), zorder=2,
               label=f"other matchups (N = {len(o)})")

    ax.scatter([lon], [lat], marker="*", s=320, color=FLOAT_COLOR,
               edgecolors="black", linewidths=0.8, transform=ccrs.PlateCarree(),
               zorder=3)
    east = lon > 0.5 * (extent[0] + extent[1])
    ax.annotate(f"{sel.wmo} / {sel.cycle}\n{str(m['time'])[:10]}",
                xy=(lon, lat), xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                # label on the side of the star facing the map centre
                xytext=(-12 if east else 12, -6), textcoords="offset points",
                ha="right" if east else "left", va="top",
                fontsize=10, zorder=4,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.8))
    ax.legend(loc="upper left", frameon=True, framealpha=0.85, edgecolor="none")
    # explicit y: matplotlib's automatic title placement returns y = inf
    # next to cartopy's gridline labels, which hides the title
    ax.set_title("(b) Float position", loc="left", y=1.0, pad=6)


def _extent_with_float(extent, lon, lat, margin: float = MAP_MARGIN):
    """Grow ``extent`` so the float is at least ``margin`` degrees inside."""
    lon0, lon1, lat0, lat1 = extent
    return (min(lon0, lon - margin), max(lon1, lon + margin),
            min(lat0, lat - margin), max(lat1, lat + margin))


# ── figure ────────────────────────────────────────────────────────────────────

def fig_argo_profile(wmo: int, cycle: int, out=None,
                     db=None, pmax: float | None = None, extent=MAP_EXTENT,
                     sel=None, layers=None, others: pd.DataFrame | None = None):
    """Two-panel figure: the b_bp(700) profile and the float's position.

    Args:
        wmo, cycle: The float profile.
        out: Path to save the PNG; nothing is saved if ``None``.
        db: Path to ``pab.db``; default :data:`DEFAULT_DB`.
        pmax: Bottom of the profile panel (dbar). Default max(2 MLD,
            :data:`PMAX_MIN`), or :data:`NO_MLD_DEPTH` without an MLD (Q2).
        extent: Map extent (lon_min, lon_max, lat_min, lat_max).
        sel, layers, others: Pre-loaded data (skip the DB read / fetch).

    Returns:
        The matplotlib Figure.
    """
    if sel is None or layers is None:
        sel, layers = load_profile(wmo, cycle, db)
    if others is None:
        others = load_matchups_in_box(db, extent)
    if pmax is None:
        pmax = max(2.0 * sel.mld, PMAX_MIN) if np.isfinite(sel.mld) else NO_MLD_DEPTH
    m = sel.matchup

    with mpl.rc_context(RC):
        fig = plt.figure(figsize=(11, 5), constrained_layout=True)
        gs = fig.add_gridspec(1, 2, width_ratios=[4, 6])
        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
        _profile_panel(ax1, sel, layers, pmax)
        _map_panel(ax2, sel, others, extent)
        fig.suptitle(
            f"BGC-Argo {sel.wmo} cycle {sel.cycle}, {str(m['time'])[:10]} "
            f"(dx = {m['distance_km']:.1f} km)")   # dt dropped (Q6: dt = 20.9 h)
        if out is not None:
            # saved inside the rc context so savefig.dpi (300, Q5) applies;
            # no bbox_inches="tight": with cartopy's gridline labels it clips
            # the map, and constrained_layout already fits the figure
            fig.savefig(out)
    return fig


# ── CLI ───────────────────────────────────────────────────────────────────────

#: Figures by number: ``python fig_argo.py <n>``.
FIGURES = {
    1: "b_bp profile + float position (fig_argo_<wmo>_<cycle>.png)",
}


def main(flg: int):
    """Make figure ``flg`` with the module defaults (see :data:`FIGURES`).

    1: :func:`fig_argo_profile` for :data:`DEFAULT_WMO` / :data:`DEFAULT_CYCLE`,
       written to :data:`DEFAULT_OUT_DIR`.
    """
    if flg == 1:
        #: The profile JXP chose (Q1).
        DEFAULT_WMO, DEFAULT_CYCLE = 5906518, 97
        out = DEFAULT_OUT_DIR / f"fig_argo_{DEFAULT_WMO}_{DEFAULT_CYCLE}.png"
        fig = fig_argo_profile(DEFAULT_WMO, DEFAULT_CYCLE, out=out)
        plt.close(fig)
        print(f"✓ {out}")
    else:
        raise ValueError(f"Unknown figure {flg}; choose from {FIGURES}")


if __name__ == "__main__":
    # python fig_argo.py <n>; no argument means figure 1
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
