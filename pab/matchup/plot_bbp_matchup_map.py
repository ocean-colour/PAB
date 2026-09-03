"""One-off script: regional map of PACE-Argo bbp700 matchups coloured by
relative backscattering difference (PACE - Argo) / PACE.

Positive (red): PACE bbp700 > Argo bbp700
Negative (blue): Argo bbp700 > PACE bbp700
White: perfect agreement

Usage
-----
    python pab/matchup/plot_bbp_matchup_map.py \
        --db /path/to/pab.db \
        --out pace_argo_bbp700_relDiff_map.png

Defaults to the standard data-directory location if --db is omitted,
and saves to the current working directory if --out is omitted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
PAB_DB_DEFAULT = Path("/Users/alliejames/Documents/summer 2026/data/PAB/pab.db")


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=PAB_DB_DEFAULT,
                   help="Path to pab.db (default: %(default)s)")
    p.add_argument("--out", type=Path, default=Path("pace_argo_bbp700_relDiff_map.png"),
                   help="Output PNG path (default: %(default)s)")
    p.add_argument("--dpi", type=int, default=200,
                   help="Figure DPI (default: %(default)s)")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Core figure function (importable for notebooks / unit tests)
# ---------------------------------------------------------------------------

def plot_bbp_matchup_map(df, *, outfile=None, dpi: int = 200):
    """Draw a regional map of matchup positions coloured by relative bbp700 diff.

    Relative difference = (bbp_bing - bbp_argo) / bbp_bing  (PACE is bbp_bing).
    Diverging RdBu_r colormap: red = PACE > Argo, blue = Argo > PACE, white = 0.

    Args:
        df: DataFrame from :func:`pab.metrics.compare.gather_matchups` --
            must contain ``latitude``, ``longitude``, ``bbp_bing``,
            ``bbp_argo`` columns.
        outfile: Path to save the figure (``None`` -> return Figure).
        dpi: Resolution for saved file.

    Returns:
        Matplotlib Figure (or written Path when outfile is given).
    """
    # -- compute relative difference ----------------------------------------
    bbp_pace = np.asarray(df["bbp_bing"], dtype=float)
    bbp_argo = np.asarray(df["bbp_argo"], dtype=float)
    rel_diff = (bbp_pace - bbp_argo) / bbp_pace   # (PACE - Argo) / PACE

    lon = np.asarray(df["longitude"], dtype=float)
    lat = np.asarray(df["latitude"], dtype=float)

    # -- color scale: symmetric around 0, driven by data maximum ------------
    abs_max = np.nanmax(np.abs(rel_diff))
    vmax = np.ceil(abs_max * 10) / 10   # round up to nearest 0.1
    vmax = max(vmax, 0.1)               # floor so scale is always visible
    vmin = -vmax

    # -- map extent: pad around data extent ---------------------------------
    lon_range = lon.max() - lon.min()
    lat_range = lat.max() - lat.min()
    lon_pad = max(lon_range * 0.4, 2.5)
    lat_pad = max(lat_range * 0.4, 2.5)
    x0, x1 = lon.min() - lon_pad, lon.max() + lon_pad
    y0, y1 = lat.min() - lat_pad, lat.max() + lat_pad

    # -- figure setup --------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_facecolor("#cce5f5")  # ocean blue background

    # Degree/hemisphere tick labels
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{abs(v):.0f}\u00b0{'W' if v < 0 else 'E'}"))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{abs(v):.0f}\u00b0{'S' if v < 0 else 'N'}"))
    ax.grid(linewidth=0.5, color="#aaaaaa", alpha=0.6, linestyle="--")
    ax.tick_params(labelsize=8)

    # -- scatter the matchups -----------------------------------------------
    sc = ax.scatter(
        lon, lat,
        c=rel_diff,
        cmap="RdBu_r",
        vmin=vmin, vmax=vmax,
        s=150,
        edgecolors="k", linewidths=0.8,
        zorder=5,
    )

    # -- label each point with cycle number (above dot) ---------------------
    if "cycle" in df.columns:
        for _, row in df.iterrows():
            ax.annotate(
                f"c{int(row['cycle'])}",
                xy=(row["longitude"], row["latitude"]),
                fontsize=7.5, color="#111111",
                ha="center", va="bottom",
                xytext=(0, 8), textcoords="offset points",
                zorder=6,
            )

    # -- add per-point relative-difference value below each dot -------------
    for i in range(len(df)):
        ax.annotate(
            f"{rel_diff[i]:+.2f}",
            xy=(lon[i], lat[i]),
            fontsize=6.5, color="#111111",
            ha="center", va="top",
            xytext=(0, -9), textcoords="offset points",
            zorder=6,
        )

    # -- colorbar ------------------------------------------------------------
    cbar = fig.colorbar(sc, ax=ax, orientation="vertical",
                        fraction=0.03, pad=0.02, shrink=0.85)
    cbar.set_label(
        r"$(b_{bp}^{\rm PACE} - b_{bp}^{\rm Argo})\;/\;b_{bp}^{\rm PACE}$",
        fontsize=10,
    )
    cbar.ax.axhline(0, color="k", lw=0.8, ls="--")
    cbar.ax.tick_params(labelsize=8)

    # -- title + axis labels -------------------------------------------------
    n = len(df)
    wmo_list = (", ".join(str(w) for w in sorted(df["wmo"].unique()))
                if "wmo" in df.columns else "?")
    ax.set_title(
        f"PACE - Argo bbp700 relative difference  (n = {n}, WMO {wmo_list})\n"
        r"Red: PACE $>$ Argo  |  Blue: Argo $>$ PACE  |  White: agreement",
        fontsize=10, pad=8,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    fig.tight_layout()

    # -- save or return -------------------------------------------------------
    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    args = _parse_args(argv)

    if not args.db.exists():
        sys.exit(f"ERROR: pab.db not found at {args.db}. Pass --db <path>.")

    from pab.db.store import Store
    from pab.metrics.compare import gather_matchups

    print(f"Opening {args.db}")
    with Store.open(args.db, create=False) as store:
        df = gather_matchups(store)

    if df.empty:
        sys.exit("No matchups with BING fits found -- nothing to plot.")

    print(f"Found {len(df)} matchup(s):")
    for _, row in df.iterrows():
        rd = (row["bbp_bing"] - row["bbp_argo"]) / row["bbp_bing"]
        print(f"  WMO {row['wmo']} cycle {row['cycle']:>3d}  "
              f"lat={row['latitude']:.3f}  lon={row['longitude']:.3f}  "
              f"bbp_pace={row['bbp_bing']:.6f}  bbp_argo={row['bbp_argo']:.6f}  "
              f"relDiff={rd:+.3f}")

    plot_bbp_matchup_map(df, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
