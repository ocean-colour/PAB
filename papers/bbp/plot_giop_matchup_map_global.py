"""
Global Mollweide map of PACE–Argo bbp700 matchups colored by GIOP relative difference.

Usage:
    python plot_giop_matchup_map_global.py
    python plot_giop_matchup_map_global.py --db /path/to/pab_full.db --out /path/to/output.png
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
DEFAULT_OUT     = "/Users/alliejames/Documents/summer 2026/data/PAB/pace_argo_bbp700_global_map_giop.png"


def load_data(db=None, parquet=None):
    # Argo bbp + location from parquet
    par = pd.read_parquet(parquet or DEFAULT_PARQUET)
    par = par[['matchup_id', 'wmo', 'latitude', 'longitude', 'bbp_argo']].copy()

    # GIOP bbp442 + spectral slope from db
    con = sqlite3.connect(db or DEFAULT_DB)
    giop = pd.read_sql("""
        SELECT f.matchup_id,
            MAX(CASE WHEN r.quantity='NASA_GIOP_bbp_442' THEN r.value END) AS bbp442,
            MAX(CASE WHEN r.quantity='NASA_GIOP_bbp_s'   THEN r.value END) AS bbp_s
        FROM fits f
        JOIN fit_results r ON f.fit_id = r.fit_id
        WHERE f.algorithm = 'NASA_GIOP'
        GROUP BY f.matchup_id
    """, con)
    con.close()

    giop = giop.dropna(subset=['bbp442', 'bbp_s'])
    giop['bbp_giop'] = giop['bbp442'] * (442 / 700) ** giop['bbp_s']

    df = par.merge(giop, on='matchup_id', how='inner')
    df = df.dropna(subset=['bbp_argo', 'bbp_giop'])
    df = df[(df['bbp_argo'] > 0) & (df['bbp_giop'] > 0)].copy()
    df['rel_diff'] = (df['bbp_giop'] - df['bbp_argo']) / df['bbp_giop']
    df = df[df['rel_diff'] >= -1.5].copy()
    return df


def make_map(df, out=DEFAULT_OUT):
    n = len(df)
    n_floats = df['wmo'].nunique()

    fig = plt.figure(figsize=(12, 5))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mollweide())
    ax.add_feature(cfeature.LAND, facecolor='#d8d8d8', zorder=1)
    ax.add_feature(cfeature.OCEAN, facecolor='#f0f4f8', zorder=0)
    ax.coastlines(lw=0.4, zorder=2)

    sc = ax.scatter(
        df['longitude'], df['latitude'],
        c=df['rel_diff'], cmap='RdBu_r',
        norm=TwoSlopeNorm(vcenter=0, vmin=-1.0, vmax=1.0),
        s=8, alpha=0.7, linewidths=0,
        transform=ccrs.PlateCarree(), zorder=3
    )
    fig.colorbar(sc, ax=ax, orientation='vertical', fraction=0.03, pad=0.04,
                 label=r'Relative $\Delta b_{bp}$ = (GIOP $-$ Argo) / GIOP')
    ax.set_title(
        f'Global distribution of PACE–Argo $b_{{bp,700}}$ matchups (GIOP)\n'
        f'n = {n:,}, {n_floats} floats',
        fontsize=10
    )
    ax.spines['geo'].set_linewidth(0.8)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',      default=None)
    parser.add_argument('--parquet', default=None)
    parser.add_argument('--out',     default=DEFAULT_OUT)
    args = parser.parse_args()
    df = load_data(db=args.db, parquet=args.parquet)
    print(f"Loaded {len(df):,} matchups from {df['wmo'].nunique()} floats")
    make_map(df, out=args.out)
