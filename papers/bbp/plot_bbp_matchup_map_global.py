"""
Global Mollweide map of PACE–Argo bbp700 matchups, colored by relative difference.
Reads from matchup_summary.parquet (default) or a pab.db SQLite database.

Usage:
    python plot_bbp_matchup_map_global.py
    python plot_bbp_matchup_map_global.py --parquet /path/to/matchup_summary.parquet
    python plot_bbp_matchup_map_global.py --db /path/to/pab.db --out /path/to/output.png
"""
import argparse
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import cartopy.crs as ccrs
import cartopy.feature as cfeature

DEFAULT_PARQUET = "/Users/alliejames/Documents/summer 2026/data/PAB/matchup_summary.parquet"
DEFAULT_OUT = "/Users/alliejames/Documents/summer 2026/data/PAB/pace_argo_bbp700_global_map.png"

def load_data(parquet=None, db=None):
    import pandas as pd
    if db:
        import sqlite3
        con = sqlite3.connect(db)
        df = pd.read_sql("""
            SELECT m.matchup_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time,
                   f.chisq, s.bbp700 AS bbp_argo, s.chla,
                   r.bbp_bing, r.bbp_bing_lo, r.bbp_bing_hi
            FROM matchups m
            JOIN profiles p ON m.profile_id = p.profile_id
            JOIN fits f ON m.matchup_id = f.matchup_id
            JOIN mld_summary s ON m.profile_id = s.profile_id
            JOIN (
                SELECT fit_id,
                    MAX(CASE WHEN param='bbp700' THEN val END) AS bbp_bing,
                    MAX(CASE WHEN param='bbp700_lo' THEN val END) AS bbp_bing_lo,
                    MAX(CASE WHEN param='bbp700_hi' THEN val END) AS bbp_bing_hi
                FROM fit_results GROUP BY fit_id
            ) r ON f.fit_id = r.fit_id
        """, con)
        con.close()
    else:
        path = parquet or DEFAULT_PARQUET
        df = pd.read_parquet(path)
    df['time'] = pd.to_datetime(df['time'])
    df['rel_diff'] = (df['bbp_bing'] - df['bbp_argo']) / df['bbp_bing']
    valid = df.dropna(subset=['bbp_argo', 'bbp_bing']).copy()
    valid = valid[valid['rel_diff'] >= -1.5].copy()
    return valid


AOML_INDEX_URL = "https://data-argo.ifremer.fr/argo_bio-profile_index.txt.gz"

def get_aoml_wmos():
    import requests, gzip, pandas as pd
    r = requests.get(AOML_INDEX_URL, timeout=120)
    content = gzip.decompress(r.content).decode('utf-8')
    lines = [l for l in content.split('\n') if l and not l.startswith('#')]
    rows = [l.split(',') for l in lines[1:] if l]
    idx = pd.DataFrame(rows, columns=lines[0].split(','))
    idx['dac'] = idx['file'].str.split('/').str[0]
    idx['wmo'] = pd.to_numeric(idx['file'].str.split('/').str[1], errors='coerce')
    return set(idx[idx['dac'] == 'aoml']['wmo'].dropna().astype(int).unique())


def make_map(df, out=DEFAULT_OUT, aoml_only=False):
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
                 label=r'Relative $\Delta b_{bp}$ = (PACE $-$ Argo) / PACE')
    label = 'AOML BGC-Argo' if aoml_only else 'Argo'
    ax.set_title(
        f'Global distribution of PACE–{label} $b_{{bp,700}}$ matchups\nn = {n}, {n_floats} floats',
        fontsize=10
    )
    ax.spines['geo'].set_linewidth(0.8)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--parquet', default=None)
    parser.add_argument('--db', default=None)
    parser.add_argument('--out', default=DEFAULT_OUT)
    parser.add_argument('--aoml-only', action='store_true',
                        help='Restrict to AOML BGC-Argo floats only')
    args = parser.parse_args()
    df = load_data(parquet=args.parquet, db=args.db)
    if args.aoml_only:
        print("Fetching AOML float list from Argo GDAC...")
        aoml_wmos = get_aoml_wmos()
        df = df[df['wmo'].isin(aoml_wmos)].copy()
        print(f"Filtered to {df['wmo'].nunique()} AOML floats")
    print(f"Loaded {len(df)} valid matchups from {df['wmo'].nunique()} floats")
    out = args.out
    if args.aoml_only and out == DEFAULT_OUT:
        out = DEFAULT_OUT.replace('.png', '_aoml.png')
    make_map(df, out=out, aoml_only=args.aoml_only)
