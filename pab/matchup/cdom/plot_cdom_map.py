"""Global map of CDOM-matchup locations, colored by raw Argo CDOM magnitude.

Descriptive only — color encodes CDOM concentration (ppb QSDE), not a
PACE-vs-Argo difference (per C3, no bias metric exists for CDOM). Shows where
the ~48%-of-fleet CDOM coverage actually falls and whether high/low CDOM
clusters regionally (river plumes, high latitudes, etc.).

Usage
-----
    python pab/matchup/cdom/plot_cdom_map.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pab.matchup.cdom.data import DEFAULT_DB, SEABIRD_CAVEAT, valid_cdom
from pab.matchup.chl.data import load_chl_matchups


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("cdom_global_map.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_cdom_map(df, *, outfile=None, dpi: int = 200):
    """Mollweide map, color = log10(Argo CDOM) — magnitude only, not a bias."""
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    lon = df["longitude"].to_numpy(dtype=float)
    lat = df["latitude"].to_numpy(dtype=float)
    log_cdom = np.log10(df["cdom"].to_numpy(dtype=float))

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
        c=log_cdom,
        cmap="viridis",
        s=12,
        alpha=0.65,
        transform=ccrs.PlateCarree(),
        zorder=5,
    )
    cbar = fig.colorbar(
        sc, orientation="horizontal", fraction=0.04, pad=0.05, shrink=0.7
    )
    cbar.set_label(r"log$_{10}$(Argo CDOM) [ppb QSDE]")
    ax.set_title(
        f"CDOM matchup coverage  (n = {len(df)}, ~{100 * len(df) / 14609:.0f}% of the full Chl-a matchup set)\n"
        "Color = raw Argo CDOM magnitude (not a PACE comparison)",
        fontsize=11,
    )
    fig.tight_layout()
    # Placed relative to the colorbar's own axis (not the figure), well below
    # its label, so it never collides with the colorbar regardless of layout.
    cbar.ax.text(
        0.5,
        -3.2,
        SEABIRD_CAVEAT,
        transform=cbar.ax.transAxes,
        ha="center",
        va="top",
        fontsize=7.5,
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
    df = valid_cdom(df)
    print(f"Loaded {len(df)} valid CDOM matchups")
    plot_cdom_map(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
