"""
Figure 10: BING-predicted Rrs(700 nm) vs. relative bias δ, colored by matchup date.

BING-predicted Rrs(700) is computed from the posterior median anw700 and bbp700
using the Gordon et al. (1988) radiative transfer approximation:
    u = bbp / (anw + bbp + 0.0026)   # 0.0026 = pure water bbw at 700 nm
    Rrs_pred = 0.0949 * u + 0.0794 * u**2

Usage:
    python plot_rrs700_vs_delta.py
    python plot_rrs700_vs_delta.py --db /path/to/pab.db --out /path/to/out.png
"""
import argparse
import sqlite3
from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pab.config import DATA_DIR

DEFAULT_DB = Path(DATA_DIR) / "v2" / "pab.db"  # the v2.1 release
DEFAULT_PARQUET = Path(DATA_DIR) / "v2" / "matchup_summary.parquet"
DEFAULT_OUT = Path(DATA_DIR) / "fig10_rrs700_vs_delta.png"
BBW_700 = 0.0026  # pure water backscattering at 700 nm (m⁻¹)


def load_data(db=None, parquet=None):
    db_path = db or DEFAULT_DB
    par_path = parquet or DEFAULT_PARQUET

    # anw700 / bbp700 posterior medians per BING fit. Keyed by fit_id, not
    # matchup_id: the v2 DB holds a 2.0, a 2.0.1 and a 2.1 fit for the same
    # matchup, and the parquet's fit_id names the one the release reports.
    con = sqlite3.connect(db_path)
    anw = pd.read_sql(
        """SELECT f.fit_id,
                  MAX(CASE WHEN fr.quantity='BING_ExpBPow_anw700' THEN fr.value END) AS anw700,
                  MAX(CASE WHEN fr.quantity='BING_ExpBPow_bbp700' THEN fr.value END) AS bbp700_fit
           FROM fits f
           JOIN fit_results fr ON fr.fit_id = f.fit_id
           WHERE f.algorithm = 'BING'
           GROUP BY f.fit_id""",
        con,
    )
    con.close()

    par = pd.read_parquet(par_path)
    par = par.dropna(subset=["bbp_argo", "bbp_bing"])
    par = par[(par["bbp_argo"] > 0) & (par["bbp_bing"] > 0)].copy()
    par["delta"] = (par["bbp_bing"] - par["bbp_argo"]) / par["bbp_bing"]
    par = par[par["delta"].between(-1.5, 1.0)]
    par["time"] = pd.to_datetime(par["time"])

    df = par.merge(anw, on="fit_id", how="inner")
    df = df.dropna(subset=["anw700", "bbp700_fit"])

    # Compute BING-predicted Rrs(700)
    bbp = df["bbp700_fit"].values
    anw_v = df["anw700"].values
    u = bbp / (anw_v + bbp + BBW_700)
    df["rrs700_pred"] = 0.0949 * u + 0.0794 * u ** 2

    return df


def make_figure(df, out=None):
    times_num = mdates.date2num(df["time"])
    RC = {
        "font.size": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "figure.dpi": 180, "axes.linewidth": 0.8,
    }

    with mpl.rc_context(RC):
        fig, ax = plt.subplots(figsize=(7, 5))
        sc = ax.scatter(
            df["delta"], df["rrs700_pred"],
            c=times_num, cmap="viridis",
            s=4, alpha=0.4, linewidths=0, rasterized=True,
        )
        ax.axvline(0, color="black", lw=0.8, ls="--")
        ax.set_xlabel(r"$\delta$ = (PACE $-$ Argo) / PACE")
        ax.set_ylabel(r"BING-predicted $R_{rs}$(700 nm) (sr$^{-1}$)")
        ax.set_title(
            r"BING $R_{rs}$(700 nm) vs $\delta$" + "\ncolored by matchup date",
            fontsize=9,
        )
        ax.set_xlim(-1.05, 1.05)
        ax.grid(True, lw=0.4, alpha=0.5, color="#cccccc")
        ax.set_axisbelow(True)

        cbar = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.03)
        cbar.set_label("Matchup time", rotation=270, labelpad=14)
        tick_locs = np.linspace(times_num.min(), times_num.max(), 6)
        cbar.set_ticks(tick_locs)
        cbar.set_ticklabels(
            [mdates.num2date(t).strftime("%Y-%m-%d") for t in tick_locs]
        )

        fig.tight_layout()
        outpath = out or DEFAULT_OUT
        fig.savefig(outpath, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved → {outpath}  (n={len(df):,})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    parser.add_argument("--parquet", default=None)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    df = load_data(db=args.db, parquet=args.parquet)
    make_figure(df, out=args.out)
