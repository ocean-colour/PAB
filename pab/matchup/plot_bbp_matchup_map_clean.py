"""Global Mollweide map of high-quality PACE-Argo bbp700 matchups.

Quality filter applied:
  - granule cloud cover < 50 %
  - BING reduced chi-squared < 1.0
  - valid (non-NaN) Argo bbp700

Usage
-----
    python pab/matchup/plot_bbp_matchup_map_clean.py
    python pab/matchup/plot_bbp_matchup_map_clean.py --db /path/to/pab.db --cc 50 --chisq 1.0
"""

from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

PAB_DB_DEFAULT = Path("/Users/alliejames/Documents/summer 2026/data/PAB/pab.db")
OUT_DEFAULT    = Path("/Users/alliejames/Documents/summer 2026/data/PAB/pace_argo_bbp700_clean_map.png")


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",    type=Path,  default=PAB_DB_DEFAULT)
    p.add_argument("--out",   type=Path,  default=OUT_DEFAULT)
    p.add_argument("--dpi",   type=int,   default=200)
    p.add_argument("--cc",    type=float, default=50.0,
                   help="Max cloud cover %% (default 50)")
    p.add_argument("--chisq", type=float, default=1.2,
                   help="Max BING reduced chi-squared (default 1.2)")
    return p.parse_args(argv)


def plot_clean_map(df, *, cc_thresh=50.0, chisq_thresh=1.0, outfile=None, dpi=200):
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    bbp_pace = np.asarray(df["bbp_bing"],    dtype=float)
    bbp_argo = np.asarray(df["bbp_argo"],    dtype=float)
    rd  = (bbp_pace - bbp_argo) / bbp_pace
    cc  = np.asarray(df["cloud_cover"],      dtype=float)
    chi = np.asarray(df["chisq"],            dtype=float)
    lon = np.asarray(df["longitude"],        dtype=float)
    lat = np.asarray(df["latitude"],         dtype=float)

    good = np.isfinite(rd) & np.isfinite(bbp_argo) & (cc < cc_thresh) & (chi < chisq_thresh)
    n_all  = np.isfinite(rd).sum()
    n_good = good.sum()
    print(f"Total valid matchups: {n_all}  →  after quality filter: {n_good}")

    proj = ccrs.Mollweide()
    fig  = plt.figure(figsize=(12, 6))
    ax   = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_global()
    ax.add_feature(cfeature.LAND,  facecolor="#cccccc", edgecolor="none")
    ax.add_feature(cfeature.OCEAN, facecolor="white")
    ax.coastlines(linewidth=0.5, color="#555555")
    ax.spines["geo"].set_linewidth(0.8)

    norm = mpl.colors.Normalize(vmin=-1, vmax=1)
    sc = ax.scatter(
        lon[good], lat[good], c=rd[good],
        cmap="RdBu_r", norm=norm,
        s=30, alpha=0.9,
        edgecolors="k", linewidths=0.4,
        transform=ccrs.PlateCarree(), zorder=5,
    )

    cbar = fig.colorbar(sc, ax=ax, orientation="horizontal",
                        fraction=0.04, pad=0.05, shrink=0.7, extend="both")
    cbar.set_label(r"Relative $\Delta b_{bp}$ = (PACE $-$ Argo) / PACE", fontsize=11)
    cbar.ax.tick_params(labelsize=9)

    ax.set_title(
        f"High-quality PACE–Argo bbp700 matchups  (n = {n_good} of {n_all})\n"
        rf"Filter: cloud cover < {cc_thresh:.0f}%  &  BING $\chi^2_r$ < {chisq_thresh}",
        fontsize=11,
    )
    fig.suptitle(r"Relative $\Delta b_{bp}$ = (PACE $-$ Argo) / PACE",
                 fontsize=13, y=1.01)
    fig.tight_layout()

    if outfile is not None:
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved → {outfile}")
    return fig


def main(argv=None):
    args = _parse_args(argv)
    if not args.db.exists():
        raise FileNotFoundError(f"pab.db not found at {args.db}")

    from pab.db.store import Store
    from pab.metrics.compare import gather_matchups

    with Store.open(args.db, create=False) as store:
        df = gather_matchups(store)
        meta = store.query_df("""
            SELECT m.matchup_id, g.cloud_cover
            FROM matchups m
            JOIN granules g ON g.granule_id = m.granule_id
        """)
    df = df.merge(meta, on="matchup_id", how="left")

    plot_clean_map(df, cc_thresh=args.cc, chisq_thresh=args.chisq,
                   outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
