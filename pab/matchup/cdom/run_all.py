"""Run the full CDOM qualitative/correlative figure set and print the headline stats.

Usage
-----
    python pab/matchup/cdom/run_all.py --outdir pab/matchup/cdom
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scipy import stats

from pab.matchup.cdom import (
    plot_cdom_map,
    plot_cdom_regional,
    plot_cdom_scatter,
    plot_cdom_seasonal,
)
from pab.matchup.cdom.data import DEFAULT_DB, valid_cdom
from pab.matchup.chl.data import load_chl_matchups


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--outdir", type=Path, default=Path("."))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    args.outdir.mkdir(parents=True, exist_ok=True)

    full = load_chl_matchups(args.db)
    df = valid_cdom(full)
    print(
        f"{len(df)} of {len(full)} matchups ({100 * len(df) / len(full):.1f}%) have both a valid raw CDOM and a fitted Adg"
    )
    print(
        f"cdom_data_mode breakdown:\n{df['cdom_data_mode'].value_counts(dropna=False)}"
    )

    rho, pval = stats.spearmanr(df["cdom"], df["adg_bing"])
    print(f"\nOverall Spearman rho = {rho:.3f} (p={pval:.2e})")
    for bas, sub in df.groupby("basin"):
        r, _ = stats.spearmanr(sub["cdom"], sub["adg_bing"])
        print(f"  {bas}: n={len(sub)}, rho={r:.2f}")
    for season, sub in df.groupby("season"):
        r, _ = stats.spearmanr(sub["cdom"], sub["adg_bing"])
        print(f"  {season}: n={len(sub)}, rho={r:.2f}")

    plot_cdom_scatter.plot_cdom_scatter(
        df, outfile=args.outdir / "cdom_vs_adg_scatter.png", dpi=args.dpi
    )
    plot_cdom_regional.plot_cdom_by_basin(
        df, outfile=args.outdir / "cdom_vs_adg_by_basin.png", dpi=args.dpi
    )
    plot_cdom_seasonal.plot_cdom_seasonal(
        df, outfile=args.outdir / "cdom_vs_adg_seasonal.png", dpi=args.dpi
    )
    plot_cdom_map.plot_cdom_map(
        df, outfile=args.outdir / "cdom_global_map.png", dpi=args.dpi
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
