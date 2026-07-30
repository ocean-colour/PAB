"""Scatter of Argo MLD bbp700 vs. mixed-layer temperature for all profiles.

One point per profile, error bars = ±1 std within the mixed layer.
Filled markers = cycles with a PACE matchup; open = no matchup.
Two floats shown in different colors.

Usage
-----
    python pab/matchup/plot_bbp700_vs_temp.py --db /path/to/pab.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

PAB_DB_DEFAULT = Path("/Users/alliejames/Documents/summer 2026/data/PAB/pab.db")


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=PAB_DB_DEFAULT)
    p.add_argument("--out", type=Path, default=Path("bbp700_vs_temp.png"))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def plot_bbp700_vs_temp(store, *, outfile=None, dpi: int = 200):
    """Scatter of MLD bbp700 vs. temperature for all profiles in the store.

    Args:
        store: Open :class:`pab.db.store.Store`.
        outfile: Save path, or ``None`` to return the Figure.
        dpi: Output resolution.

    Returns:
        Matplotlib Figure or written Path.
    """
    df = store.query_df("""
        SELECT p.wmo, p.cycle, p.time,
               ms.bbp700, ms.bbp700_std, ms.temp, ms.chla,
               CASE WHEN m.matchup_id IS NOT NULL THEN 1 ELSE 0 END AS has_matchup
        FROM profiles p
        JOIN mld_summary ms ON ms.profile_id = p.profile_id
        LEFT JOIN matchups m ON m.profile_id = p.profile_id
        ORDER BY p.wmo, p.time
    """)

    wmos = sorted(df["wmo"].unique())
    cmap = mpl.colormaps["tab10"]
    wmo_colors = {w: cmap(i) for i, w in enumerate(wmos)}
    wmo_names = {
        7902136: "WMO 7902136 (eq. Pacific)",
        7902226: "WMO 7902226 (N. Atlantic)",
    }

    fig, ax = plt.subplots(figsize=(6, 4.5))

    for wmo_id in wmos:
        sub = df[df["wmo"] == wmo_id]
        col = wmo_colors[wmo_id]
        matched = sub[sub["has_matchup"] == 1]
        unmatched = sub[sub["has_matchup"] == 0]

        for grp, is_matched in [(matched, True), (unmatched, False)]:
            if grp.empty:
                continue
            lbl = wmo_names[wmo_id] + (" (matched)" if is_matched else " (no match)")
            ax.errorbar(
                grp["temp"], grp["bbp700"], yerr=grp["bbp700_std"],
                fmt="o", color=col,
                markerfacecolor=col if is_matched else "none",
                markeredgecolor=col, markeredgewidth=1.2,
                ms=7, elinewidth=0.9, capsize=3, capthick=0.9,
                label=lbl, zorder=4,
            )

        for _, row in sub.iterrows():
            ax.annotate(
                f"c{int(row['cycle'])}",
                xy=(row["temp"], row["bbp700"]),
                xytext=(4, 4), textcoords="offset points",
                fontsize=6.5, color=col, zorder=5,
            )

    ax.set_xlabel("MLD temperature  (°C)", fontsize=9)
    ax.set_ylabel(r"MLD $b_{bp}(700)$  (m$^{-1}$)", fontsize=9)
    ax.set_title(
        "No clear temperature\u2013bbp700 relationship across both floats",
        fontsize=9, loc="left", pad=6,
    )
    ax.tick_params(labelsize=7.5, direction="out")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.25, linewidth=0.5, linestyle="--")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.margins(0.1)
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def main(argv=None):
    args = _parse_args(argv)
    from pab.db.store import Store
    with Store.open(args.db, create=False) as store:
        plot_bbp700_vs_temp(store, outfile=args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
