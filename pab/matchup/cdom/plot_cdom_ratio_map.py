"""Geographic map of the PACE/Argo CDOM ratio (Adg / CDOM) — a deliberate C3 exception.

Per R5/R8 (chl_cdom_matchups.md): every other CDOM figure in this project
avoids any cross-unit ratio or bias-like statistic, because Argo CDOM (ppb
QSDE) and BING's Adg (m^-1) have no fixed conversion (C3). This map is a
conscious, one-off exception to that rule, made explicitly at JXP's request,
and carries a prominent caveat: **the ratio's numeric value is partly an
artifact of the arbitrary unit choice, not a calibration or bias result.**

The ratio spans ~8.5 orders of magnitude on this population (verified: min
~3e-6, median ~0.013, max ~960), so a linear color scale would render nearly
every point as one color. Per R8, the color scale is a **log scale truncated
to the 5th-95th percentile** of the ratio (the central 90%) — points outside
that range are clipped to the colorbar's end colors, with `extend='both'`
marking that clipping explicitly rather than hiding it.

Population: AOML floats only, cdom < 6 ppb QSDE (per R1/R3), ratio = Adg/CDOM
(per R8).

Usage
-----
    python pab/matchup/cdom/plot_cdom_ratio_map.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from pab.matchup.cdom.data import DEFAULT_DB, restrict_to_aoml, valid_cdom
from pab.matchup.chl.data import load_chl_matchups

#: Per R5: stated prominently on the figure itself, not just in the report text.
RATIO_CAVEAT = (
    "Deliberate exception to this project's no-ratio/no-bias rule for CDOM (R5).\n"
    "Adg/CDOM mixes units with no fixed conversion — its value is partly an\n"
    "artifact of unit choice, NOT a calibration or bias result. Color clipped to\n"
    "the central 90% (5th-95th percentile) of the ratio; extreme values exist\n"
    "beyond the colorbar ends (see 'extend' arrows)."
)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("cdom_ratio_map.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_cdom_ratio_map(df, *, outfile=None, dpi: int = 200):
    """Mollweide map, color = Adg/CDOM ratio, log scale truncated to the central 90%."""
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    lon = df["longitude"].to_numpy(dtype=float)
    lat = df["latitude"].to_numpy(dtype=float)
    ratio = (df["adg_bing"] / df["cdom"]).to_numpy(dtype=float)
    n = len(df)

    lo, hi = np.percentile(ratio, [5, 95])
    norm = mpl.colors.LogNorm(vmin=lo, vmax=hi)

    proj = ccrs.Mollweide()
    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_global()
    ax.add_feature(cfeature.LAND, facecolor="#cccccc", edgecolor="none")
    ax.add_feature(cfeature.OCEAN, facecolor="white")
    ax.coastlines(linewidth=0.5, color="#555555")
    ax.spines["geo"].set_linewidth(0.8)

    sc = ax.scatter(
        lon,
        lat,
        c=ratio,
        cmap="viridis",
        norm=norm,
        s=14,
        alpha=0.7,
        transform=ccrs.PlateCarree(),
        zorder=5,
    )
    cbar = fig.colorbar(
        sc, orientation="horizontal", fraction=0.04, pad=0.05, shrink=0.7, extend="both"
    )
    # A plain LogLocator crams too many major+minor decade ticks into this
    # narrow (5th-95th percentile) range and their labels overlap; a handful
    # of evenly log-spaced major ticks (minor ticks off) stay legible.
    cbar.set_ticks(np.geomspace(lo, hi, 5))
    cbar.ax.xaxis.set_minor_locator(mpl.ticker.NullLocator())
    cbar.ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:.3g}"))
    cbar.set_label(
        r"$A_{dg}$ / CDOM  [m$^{-1}$ per ppb QSDE]  (log scale, central 90%)"
    )
    ax.set_title(
        f"Geographic pattern of the PACE/Argo CDOM ratio — AOML, cdom < 6 ppb  (n = {n})",
        fontsize=11,
    )
    fig.tight_layout()
    cbar.ax.text(
        0.5,
        -3.6,
        RATIO_CAVEAT,
        transform=cbar.ax.transAxes,
        ha="center",
        va="top",
        fontsize=7,
        color="#555555",
    )

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
    df = restrict_to_aoml(valid_cdom(df))
    print(f"Loaded {len(df)} valid CDOM/Adg matchups (AOML, cdom < 6)")
    plot_cdom_ratio_map(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
