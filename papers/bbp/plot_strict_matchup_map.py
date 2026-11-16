"""
Global map of strict PACE–Argo matchups (≤3 h, ≤1 km), colored by relative difference.

Usage:
    python plot_strict_matchup_map.py
    python plot_strict_matchup_map.py --db /path/to/pab_full.db --out /path/to/output.png
"""
import argparse
import sqlite3
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import cartopy.crs as ccrs
import cartopy.feature as cfeature

DEFAULT_DB      = "/Users/alliejames/Documents/summer 2026/data/PAB/pab_full.db"
DEFAULT_PARQUET = "/Users/alliejames/Documents/summer 2026/data/PAB/matchup_summary.parquet"
DEFAULT_OUT     = "/Users/alliejames/Documents/summer 2026/data/PAB/pace_argo_strict_matchup_map_bing.png"

DT_MAX   = 3.0   # hours
DIST_MAX = 1.0   # km


def load_data(db=DEFAULT_DB, parquet=DEFAULT_PARQUET):
    con = sqlite3.connect(db)
    geo = pd.read_sql("SELECT matchup_id, distance_km, dtime_hours FROM matchups", con)
    con.close()

    par = pd.read_parquet(parquet)
    par['rel_diff'] = (par['bbp_bing'] - par['bbp_argo']) / par['bbp_bing']
    par = par.dropna(subset=['bbp_argo', 'bbp_bing'])
    par = par[(par['bbp_argo'] > 0) & (par['bbp_bing'] > 0)]

    merged = par.merge(geo, on='matchup_id')
    strict = merged[
        (merged['dtime_hours'] <= DT_MAX) &
        (merged['distance_km'] <= DIST_MAX)
    ].copy()
    return strict


def make_map(df, out=DEFAULT_OUT):
    n = len(df)
    n_floats = df['wmo'].nunique()
    print(f"Strict matchups: n={n}, {n_floats} floats")

    fig = plt.figure(figsize=(12, 5))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mollweide())
    ax.add_feature(cfeature.LAND, facecolor='#d8d8d8', zorder=1)
    ax.add_feature(cfeature.OCEAN, facecolor='#f0f4f8', zorder=0)
    ax.coastlines(lw=0.4, zorder=2)

    sc = ax.scatter(
        df['longitude'], df['latitude'],
        c=df['rel_diff'], cmap='RdBu_r',
        norm=TwoSlopeNorm(vcenter=0, vmin=-1.0, vmax=1.0),
        s=10, alpha=0.8, linewidths=0,
        transform=ccrs.PlateCarree(), zorder=3
    )
    fig.colorbar(sc, ax=ax, orientation='vertical', fraction=0.03, pad=0.04,
                 label=r'Relative $\Delta b_{bp}$ = (PACE $-$ Argo) / PACE')
    ax.set_title(
        f'Strict matchups ($\leq${DIST_MAX:.0f} km & $\leq${DT_MAX:.0f} h)\n'
        f'Global PACE–Argo $b_{{bp,700}}$ matchups',
        fontsize=10
    )
    ax.spines['geo'].set_linewidth(0.8)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',      default=DEFAULT_DB)
    parser.add_argument('--parquet', default=DEFAULT_PARQUET)
    parser.add_argument('--out',     default=DEFAULT_OUT)
    args = parser.parse_args()
    df = load_data(db=args.db, parquet=args.parquet)
    make_map(df, out=args.out)
