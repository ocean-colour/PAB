"""Run the full CDOM qualitative/correlative figure set and print the headline stats.

Per the R1-R8 refinement pass (chl_cdom_matchups.md), the population is
restricted to AOML floats with ``cdom < 6`` ppb QSDE — replacing the prior
unrestricted figures. QC-flag filtering (R2) and a sensor-model split (R6)
are both deferred to a future re-ingestion pass; neither is applied here.

Usage
-----
    python pab/matchup/cdom/run_all.py --outdir pab/matchup/cdom
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy import stats

from pab.matchup.cdom import (
    plot_cdom_linear,
    plot_cdom_map,
    plot_cdom_ratio_map,
    plot_cdom_regional,
    plot_cdom_scatter,
    plot_cdom_seasonal,
)
from pab.matchup.cdom.data import DEFAULT_DB, restrict_to_aoml, valid_cdom
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
    unrestricted = valid_cdom(full)
    df = restrict_to_aoml(unrestricted)
    print(
        f"{len(unrestricted)} of {len(full)} matchups have a valid raw CDOM (< 6 ppb) and a fitted Adg"
    )
    print(
        f"{len(df)} of {len(unrestricted)} are AOML-processed — the R1/R3 refined population used below"
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

    ratio = df["adg_bing"] / df["cdom"]
    print(
        f"\nAdg/CDOM ratio: p5={np.percentile(ratio, 5):.4g}, "
        f"median={ratio.median():.4g}, p95={np.percentile(ratio, 95):.4g}"
    )
    slope, intercept = np.polyfit(df["cdom"], df["adg_bing"], 1)
    print(f"Illustrative OLS fit (R4/R7): Adg = {slope:.4f}*CDOM + {intercept:.4f}")

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
    plot_cdom_linear.plot_cdom_linear(
        df, outfile=args.outdir / "cdom_vs_adg_linear.png", dpi=args.dpi
    )
    plot_cdom_ratio_map.plot_cdom_ratio_map(
        df, outfile=args.outdir / "cdom_ratio_map.png", dpi=args.dpi
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
