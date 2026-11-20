"""
Generate all global cartopy maps for the PACE–Argo bbp700 paper.

Maps produced:
  fig2_global_map_bing.png      — All BING matchups, colored by δ = (PACE-Argo)/PACE
  fig14_global_map_giop.png     — All GIOP matchups, colored by δ_GIOP
  fig15_strict_map_giop.png     — Strict GIOP matchups (≤1 km, ≤3 h)
  fig_strict_map_bing.png       — Strict BING matchups (≤1 km, ≤3 h)

Requires cartopy — run locally (not in sandbox).

Usage:
    python plot_global_maps.py
    python plot_global_maps.py --which bing giop
    python plot_global_maps.py --db /path/to/pab.db --out-dir /path/to/output/
"""
import argparse
import sqlite3
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ImportError:
    raise ImportError("cartopy is required: conda install cartopy")

# ── Default paths ─────────────────────────────────────────────────────────────
from pab.config import DATA_DIR

_DATA = Path(DATA_DIR) / "v2"               # the v2.1 release ($PAB_DATA_DIR/v2/)

DEFAULT_PARQUET = _DATA / "matchup_summary.parquet"
DEFAULT_DB      = _DATA / "pab.db"
DEFAULT_OUT     = _DATA


# ── Shared colormap ───────────────────────────────────────────────────────────
CMAP  = mpl.colormaps["RdBu_r"]
NORM  = mcolors.TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0)


def _base_map(ax):
    ax.add_feature(cfeature.LAND, facecolor="#d9d9d9", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="#f0f4f8", zorder=0)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.4, zorder=1)
    ax.gridlines(draw_labels=False, linewidth=0.3, color="#aaaaaa",
                 alpha=0.5, linestyle="--")
    ax.spines["geo"].set_linewidth(0.8)


# ── BING full dataset ─────────────────────────────────────────────────────────
def plot_bing_global(parquet, out_dir):
    df = pd.read_parquet(parquet)
    df = df.dropna(subset=["bbp_argo", "bbp_bing"])
    df = df[(df["bbp_argo"] > 0) & (df["bbp_bing"] > 0)].copy()
    df["delta"] = (df["bbp_bing"] - df["bbp_argo"]) / df["bbp_bing"]
    df = df[df["delta"].between(-1.5, 1.0)]
    n, nf = len(df), df["wmo"].nunique()

    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mollweide())
    _base_map(ax)
    sc = ax.scatter(df["longitude"], df["latitude"],
                    c=df["delta"], cmap=CMAP, norm=NORM,
                    s=4, alpha=0.7, linewidths=0,
                    transform=ccrs.PlateCarree(), zorder=2, rasterized=True)
    cbar = fig.colorbar(sc, ax=ax, orientation="vertical",
                        fraction=0.03, pad=0.03, shrink=0.85)
    cbar.set_label(r"$\delta$ = (PACE $-$ Argo) / PACE", rotation=270,
                   labelpad=14, fontsize=9)
    ax.set_title(
        r"Global distribution of PACE–Argo $b_{bp,700}$ matchups (BING)"
        f"\nn = {n:,}, {nf} floats",
        fontsize=10,
    )
    fig.tight_layout()
    out = Path(out_dir) / "fig2_global_map_bing.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out}  (n={n:,}, {nf} floats)")


# ── GIOP full dataset ─────────────────────────────────────────────────────────
def plot_giop_global(parquet, db, out_dir):
    con = sqlite3.connect(db)
    giop = pd.read_sql(
        """SELECT f.matchup_id,
                  MAX(CASE WHEN fr.quantity='NASA_GIOP_bbp_442' THEN fr.value END) AS giop_bbp442,
                  MAX(CASE WHEN fr.quantity='NASA_GIOP_bbp_s'   THEN fr.value END) AS giop_bbp_s
           FROM fits f
           JOIN fit_results fr ON fr.fit_id = f.fit_id
           WHERE f.algorithm = 'NASA_GIOP'
           GROUP BY f.matchup_id""",
        con,
    )
    con.close()

    par = pd.read_parquet(parquet)
    par = par.dropna(subset=["bbp_argo"])
    par = par[par["bbp_argo"] > 0].copy()

    df = par.merge(giop, on="matchup_id", how="inner")
    df = df.dropna(subset=["giop_bbp442", "giop_bbp_s"])
    df = df[df["giop_bbp442"] > 0].copy()
    df["bbp_giop700"] = df["giop_bbp442"] * (442 / 700) ** df["giop_bbp_s"]
    df = df[df["bbp_giop700"] > 0]
    df["delta"] = (df["bbp_giop700"] - df["bbp_argo"]) / df["bbp_giop700"]
    df = df[df["delta"].between(-1.5, 1.0)]
    n, nf = len(df), df["wmo"].nunique()

    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mollweide())
    _base_map(ax)
    sc = ax.scatter(df["longitude"], df["latitude"],
                    c=df["delta"], cmap=CMAP, norm=NORM,
                    s=4, alpha=0.7, linewidths=0,
                    transform=ccrs.PlateCarree(), zorder=2, rasterized=True)
    cbar = fig.colorbar(sc, ax=ax, orientation="vertical",
                        fraction=0.03, pad=0.03, shrink=0.85)
    cbar.set_label(r"$\delta$ = (GIOP $-$ Argo) / GIOP", rotation=270,
                   labelpad=14, fontsize=9)
    ax.set_title(
        r"Global distribution of PACE–Argo $b_{bp,700}$ matchups (GIOP)"
        f"\nn = {n:,}, {nf} floats",
        fontsize=10,
    )
    fig.tight_layout()
    out = Path(out_dir) / "fig14_global_map_giop.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out}  (n={n:,}, {nf} floats)")


# ── Strict maps (≤1 km, ≤3 h) ────────────────────────────────────────────────
def _plot_strict(parquet, db, algorithm, delta_col, label, outname, out_dir):
    con = sqlite3.connect(db)
    geo = pd.read_sql(
        "SELECT matchup_id, distance_km, dtime_hours FROM matchups", con
    )

    if algorithm == "GIOP":
        giop = pd.read_sql(
            """SELECT f.matchup_id,
                      MAX(CASE WHEN fr.quantity='NASA_GIOP_bbp_442' THEN fr.value END) AS giop_bbp442,
                      MAX(CASE WHEN fr.quantity='NASA_GIOP_bbp_s'   THEN fr.value END) AS giop_bbp_s
               FROM fits f
               JOIN fit_results fr ON fr.fit_id = f.fit_id
               WHERE f.algorithm = 'NASA_GIOP'
               GROUP BY f.matchup_id""",
            con,
        )
    con.close()

    par = pd.read_parquet(parquet)
    par = par.dropna(subset=["bbp_argo"])
    par = par[par["bbp_argo"] > 0].copy()

    if algorithm == "GIOP":
        df = par.merge(giop, on="matchup_id", how="inner")
        df = df.dropna(subset=["giop_bbp442", "giop_bbp_s"])
        df = df[df["giop_bbp442"] > 0].copy()
        df["bbp_sat"] = df["giop_bbp442"] * (442 / 700) ** df["giop_bbp_s"]
        df["delta"] = (df["bbp_sat"] - df["bbp_argo"]) / df["bbp_sat"]
        sym = "GIOP"
    else:
        df = par.dropna(subset=["bbp_bing"])
        df = df[df["bbp_bing"] > 0].copy()
        df["delta"] = (df["bbp_bing"] - df["bbp_argo"]) / df["bbp_bing"]
        sym = "BING"

    df = df.merge(geo, on="matchup_id", how="left")
    df = df[(df["distance_km"] <= 1.0) & (df["dtime_hours"] <= 3.0)]
    df = df[df["delta"].between(-1.5, 1.0)]
    n, nf = len(df), df["wmo"].nunique()

    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mollweide())
    _base_map(ax)
    sc = ax.scatter(df["longitude"], df["latitude"],
                    c=df["delta"], cmap=CMAP, norm=NORM,
                    s=6, alpha=0.75, linewidths=0,
                    transform=ccrs.PlateCarree(), zorder=2)
    cbar = fig.colorbar(sc, ax=ax, orientation="vertical",
                        fraction=0.03, pad=0.03, shrink=0.85)
    cbar.set_label(
        rf"$\delta$ = ({sym} $-$ Argo) / {sym}", rotation=270,
        labelpad=14, fontsize=9,
    )
    ax.set_title(
        rf"Strict matchups ($\leq$1 km & $\leq$3 h) — {sym}"
        f"\nn = {n:,}, {nf} floats",
        fontsize=10,
    )
    fig.tight_layout()
    out = Path(out_dir) / outname
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out}  (n={n:,}, {nf} floats)")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parquet", default=str(DEFAULT_PARQUET))
    parser.add_argument("--db",      default=str(DEFAULT_DB))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--which", nargs="+",
                        choices=["bing", "giop", "strict_giop", "strict_bing"],
                        default=["bing", "giop", "strict_giop", "strict_bing"])
    args = parser.parse_args()

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    if "bing" in args.which:
        plot_bing_global(args.parquet, args.out_dir)
    if "giop" in args.which:
        plot_giop_global(args.parquet, args.db, args.out_dir)
    if "strict_giop" in args.which:
        _plot_strict(args.parquet, args.db, "GIOP", "delta",
                     "Strict GIOP", "fig15_strict_map_giop.png", args.out_dir)
    if "strict_bing" in args.which:
        _plot_strict(args.parquet, args.db, "BING", "delta",
                     "Strict BING", "fig_strict_map_bing.png", args.out_dir)
