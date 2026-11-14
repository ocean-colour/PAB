"""Global maps of the Chl-a relative difference: static (cartopy) + interactive (Bokeh).

Mirrors ``pab/matchup/plot_bbp_matchup_map_clean.py`` / the bbp700 global-map
pair documented in ``pace_argo_bbp700_global_maps.md``. Per Q8, the Bokeh HTML
stays an internal artifact only (a few MB, won't render inline on GitHub) —
only the static PNG goes in the report.

Usage
-----
    python pab/matchup/chl/plot_chl_maps.py
    python pab/matchup/chl/plot_chl_maps.py --static-out chl_map.png --html-out chl_map.html
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups, valid_chl


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--static-out", type=Path, default=Path("chl_global_map.png"))
    p.add_argument("--html-out", type=Path, default=Path("chl_global_map.html"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_static_map(df, *, outfile=None, dpi: int = 200):
    """Mollweide (cartopy) global map, color = relative difference clipped ±1."""
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    lon = df["longitude"].to_numpy(dtype=float)
    lat = df["latitude"].to_numpy(dtype=float)
    rd = df["rel_diff"].to_numpy(dtype=float)

    proj = ccrs.Mollweide()
    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_global()
    ax.add_feature(cfeature.LAND, facecolor="#cccccc", edgecolor="none")
    ax.add_feature(cfeature.OCEAN, facecolor="white")
    ax.coastlines(linewidth=0.5, color="#555555")
    ax.spines["geo"].set_linewidth(0.8)

    norm = mpl.colors.Normalize(vmin=-1, vmax=1)
    sc = ax.scatter(
        lon,
        lat,
        c=np.clip(rd, -1, 1),
        cmap="RdBu_r",
        norm=norm,
        s=12,
        alpha=0.6,
        transform=ccrs.PlateCarree(),
        zorder=5,
    )
    cbar = fig.colorbar(
        sc, orientation="horizontal", fraction=0.04, pad=0.05, shrink=0.7, extend="both"
    )
    cbar.set_label("Relative difference (PACE − Argo) / PACE (chl-a)")
    ax.set_title(
        f"Global PACE-Argo Chl-a matchups (n = {len(df)})\n"
        "Red: PACE > Argo | Blue: Argo > PACE",
        fontsize=11,
    )
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def plot_interactive_map(df, *, outfile: Path):
    """CartoDB-tiled Bokeh HTML map with a hover tool (internal artifact only, per Q8)."""
    from bokeh.models import (
        ColumnDataSource,
        HoverTool,
        LinearColorMapper,
        WMTSTileSource,
    )
    from bokeh.palettes import RdBu11
    from bokeh.plotting import figure, output_file, save
    from bokeh.transform import transform

    lon = df["longitude"].to_numpy(dtype=float)
    lat = df["latitude"].to_numpy(dtype=float)
    x = lon * 20037508.34 / 180.0
    y = np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)) * 20037508.34 / np.pi

    source = ColumnDataSource(
        {
            "x": x,
            "y": y,
            "wmo": df["wmo"],
            "cycle": df["cycle"],
            "rel_diff": df["rel_diff"].clip(-1, 1),
            "rd_raw": df["rel_diff"],
            "chl_pace": df["chl_bing"],
            "chl_argo": df["chla_argo"],
            "dtime_h": df["dtime_hours"],
            "dist_km": df["distance_km"],
            "basin": df["basin"],
            "data_center": df["data_center"],
        }
    )

    mapper = LinearColorMapper(palette=RdBu11, low=-1.0, high=1.0)
    tile = WMTSTileSource(
        url="https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{Z}/{X}/{Y}.png"
    )

    p = figure(
        x_axis_type="mercator",
        y_axis_type="mercator",
        width=1000,
        height=600,
        title=f"Global PACE-Argo Chl-a matchups (n = {len(df)})",
    )
    p.add_tile(tile)
    p.scatter(
        "x", "y", source=source, color=transform("rel_diff", mapper), size=6, alpha=0.7
    )

    hover = HoverTool(
        tooltips=[
            ("Float / Cycle", "@wmo  c@cycle"),
            ("Rel. diff", "@rd_raw{+0.3f}"),
            ("PACE Chl-a", "@chl_pace{0.3f} mg/m3"),
            ("Argo Chl-a", "@chl_argo{0.3f} mg/m3"),
            ("Δt", "@dtime_h h"),
            ("Distance", "@dist_km km"),
            ("Basin", "@basin"),
            ("DAC", "@data_center"),
        ]
    )
    p.add_tools(hover)

    output_file(str(outfile))
    save(p)
    print(f"Saved -> {outfile}")
    return outfile


def main(argv=None):
    args = _parse_args(argv)
    df = load_chl_matchups(args.db)
    df = valid_chl(df, clip=1.5)
    print(f"Loaded {len(df)} valid Chl-a matchups")
    plot_static_map(df, outfile=args.static_out, dpi=args.dpi)
    plot_interactive_map(df, outfile=args.html_out)


if __name__ == "__main__":
    main()
