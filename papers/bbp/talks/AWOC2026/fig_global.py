"""
Global figures for the AWOC 2026 talk (``papers/bbp/prompts/talks/aw2026_global.md``).

Figures:
    fig_global_matchups.png -- where PACE and BGC-Argo match up (dx < 10 km,
                               dt < 3 h), coloured by the float's mixed-layer
                               Chl (raw CHLA, log scale).

Data come from the live v2.1 PAB database (``$PAB_DATA_DIR/v2/pab.db``).
Needs cartopy and cmocean (both in ocean14).

Usage:
    python papers/bbp/talks/AWOC2026/fig_global.py
    python papers/bbp/talks/AWOC2026/fig_global.py --db /path/to/pab.db --out-dir ~/Desktop/awoc/
    python papers/bbp/talks/AWOC2026/fig_global.py --dx-max 10 --dt-max 3
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pab.config import DATA_DIR

# ── defaults ──────────────────────────────────────────────────────────────────

#: The v2.1 release database.
DEFAULT_DB = Path(DATA_DIR) / "v2" / "pab.db"

#: Output directory: next to this script.
DEFAULT_OUT_DIR = Path(__file__).resolve().parent

#: Matchup definition (doc "Context"): separation and time difference.
DX_MAX_KM = 10.0
DT_MAX_H = 3.0

#: Chl colour scale (Q2): log10, clipped, cmocean "algae".
CHL_LIM = (0.01, 3.0)       # mg m^-3
CMAP_CHL = cmocean.cm.algae

#: Pacific-centred map (Q6). -155 puts the seam at 25°E (Aegean / Libya /
#: South Africa), the longitude that cuts the fewest matchups (4 within 2°).
CENTRAL_LON = -155.0

RC = {
    "font.size": 11, "axes.titlesize": 12, "figure.dpi": 150,
    "savefig.dpi": 200,
}


# ── data ──────────────────────────────────────────────────────────────────────

def load_matchups(db=None, dx_max: float = DX_MAX_KM,
                  dt_max: float = DT_MAX_H) -> pd.DataFrame:
    """Matchups within ``dx_max`` km and ``dt_max`` h, with float position and
    mixed-layer Chl.

    Args:
        db: Path to ``pab.db``; default :data:`DEFAULT_DB`.
        dx_max: Maximum float-to-pixel separation (km).
        dt_max: Maximum |float time - granule time| (h). ``dtime_hours`` is
            stored as an absolute value.

    Returns:
        One row per matchup: ``matchup_id``, ``profile_id``, ``wmo``,
        ``latitude``, ``longitude``, ``time``, ``distance_km``,
        ``dtime_hours``, ``chla`` (raw mixed-layer CHLA, mg m^-3; Q1) and
        ``chla_adjusted`` (kept for reference, not plotted).
    """
    con = sqlite3.connect(db or DEFAULT_DB)
    df = pd.read_sql(
        """SELECT m.matchup_id, m.profile_id, p.wmo, p.latitude, p.longitude,
                  p.time, m.distance_km, m.dtime_hours,
                  s.chla, s.chla_adjusted
           FROM matchups m
           JOIN profiles p USING (profile_id)
           LEFT JOIN mld_summary s USING (profile_id)
           WHERE m.distance_km < ? AND m.dtime_hours < ?""",
        con, params=(dx_max, dt_max),
    )
    con.close()
    return df


# ── map helpers ───────────────────────────────────────────────────────────────

def _base_map(ax):
    """Land, ocean, coastline and a light graticule.

    A copy of ``papers/bbp/plot_global_maps._base_map`` (Q3), so the talk
    figure does not change if the paper's map style does.
    """
    ax.add_feature(cfeature.LAND, facecolor="#d9d9d9", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="#f0f4f8", zorder=0)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.4, zorder=1)
    ax.gridlines(draw_labels=False, linewidth=0.3, color="#aaaaaa",
                 alpha=0.5, linestyle="--")
    ax.spines["geo"].set_linewidth(0.8)


# ── figures ───────────────────────────────────────────────────────────────────

def fig_global_matchups(df: pd.DataFrame, out=None, chl_lim=CHL_LIM,
                        dx_max: float = DX_MAX_KM, dt_max: float = DT_MAX_H,
                        central_lon: float = CENTRAL_LON):
    """Global map of the matchups, coloured by raw mixed-layer Chl.

    Chl is drawn on a log10 scale clipped to ``chl_lim``; values outside it
    (including Chl ≤ 0, i.e. dark-offset noise in oligotrophic water) take
    the end colours, and the colour bar's arrows say so. Profiles with no
    CHLA at all are drawn as small grey markers so every matchup appears.

    Args:
        df: Output of :func:`load_matchups`.
        out: Path to save the PNG; nothing is saved if ``None``.
        chl_lim: (min, max) of the colour scale (mg m^-3).
        dx_max, dt_max: The matchup definition, for the title.
        central_lon: Central longitude of the Mollweide map (deg E).

    Returns:
        The matplotlib Figure.
    """
    lo, hi = chl_lim
    has = df["chla"].notna()
    d = df[has].copy()
    d["chl_plot"] = d["chla"].clip(lo, hi)    # ≤ 0 and tiny values -> lo
    d = d.sort_values("chl_plot")             # high Chl drawn on top
    n, nf = len(df), df["wmo"].nunique()

    with mpl.rc_context(RC):
        fig = plt.figure(figsize=(12, 6))
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mollweide(central_longitude=central_lon))
        _base_map(ax)
        ax.set_global()

        # matchups with no CHLA: grey, underneath
        if (~has).any():
            ax.scatter(df.loc[~has, "longitude"], df.loc[~has, "latitude"],
                       s=6, c="#8a8a8a", linewidths=0, alpha=0.8,
                       transform=ccrs.PlateCarree(), zorder=2,
                       label=f"no CHLA (N = {(~has).sum():,})")

        sc = ax.scatter(d["longitude"], d["latitude"], c=d["chl_plot"],
                        cmap=CMAP_CHL, norm=mpl.colors.LogNorm(lo, hi),
                        s=10, linewidths=0.2, edgecolors="#33333355",
                        transform=ccrs.PlateCarree(), zorder=3,
                        rasterized=True)

        cbar = fig.colorbar(sc, ax=ax, orientation="vertical", extend="both",
                            fraction=0.03, pad=0.03, shrink=0.85)
        cbar.set_label(r"Argo mixed-layer Chl (mg m$^{-3}$)", rotation=270,
                       labelpad=16)
        cbar.ax.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter("%g"))

        if (~has).any():
            ax.legend(loc="lower left", frameon=False, fontsize=9)
        ax.set_title(
            f"PACE–BGC-Argo matchups (dx < {dx_max:g} km, dt < {dt_max:g} h), "
            f"N = {n:,}, {nf} floats")

    if out is not None:
        fig.savefig(out, bbox_inches="tight")
    return fig


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv=None):
    """Load the matchups and write every figure."""
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--dx-max", type=float, default=DX_MAX_KM, help="km")
    p.add_argument("--dt-max", type=float, default=DT_MAX_H, help="hours")
    args = p.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    df = load_matchups(args.db, dx_max=args.dx_max, dt_max=args.dt_max)

    out = args.out_dir / "fig_global_matchups.png"
    fig = fig_global_matchups(df, out=out, dx_max=args.dx_max, dt_max=args.dt_max)
    plt.close(fig)
    print(f"✓ {out}  (N = {len(df):,}, {df['wmo'].nunique()} floats, "
          f"{df['chla'].isna().sum()} without CHLA, {(df['chla'] <= 0).sum()} with CHLA ≤ 0)")


if __name__ == "__main__":
    main()
