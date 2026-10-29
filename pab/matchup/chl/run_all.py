"""Run the full Chl-a deep-dive figure set and print the headline statistics.

The single entry point for reproducing every figure in this subfolder (per
chl_cdom_prompt_2.md Task 1). Each figure module is also independently runnable
with its own ``--db``/``--out(dir)`` flags; this just sequences all of them
against one DB and one output directory, and prints the summary numbers a
report draft needs (n, % positive, median rel-diff, and the same broken out by
DAC/adjusted-vs-raw).

Usage
-----
    python pab/matchup/chl/run_all.py --outdir pab/matchup/chl
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from pab.matchup.chl import (
    plot_chl_adjusted,
    plot_chl_dac,
    plot_chl_diagnostics,
    plot_chl_histogram,
    plot_chl_maps,
    plot_chl_quality,
    plot_chl_scatter,
    plot_chl_stratification,
)
from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups, rel_diff, valid_chl


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--outdir", type=Path, default=Path("."))
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def _summary(df) -> str:
    n = len(df)
    rd = df["rel_diff"].to_numpy(dtype=float)
    lines = [
        f"n = {n}",
        f"% positive (PACE > Argo) = {100 * (rd > 0).mean():.1f}%",
        f"median rel_diff = {np.median(rd):+.3f}",
        f"mean rel_diff (clipped) = {np.mean(np.clip(rd, -1, 1)):+.3f}",
    ]
    if df["is_aoml"].notna().any():
        aoml = df.loc[df["is_aoml"], "rel_diff"]
        other = df.loc[(~df["is_aoml"]) & df["data_center"].notna(), "rel_diff"]
        lines.append(f"AOML median = {aoml.median():+.3f} (n={len(aoml)})")
        lines.append(f"other-DAC median = {other.median():+.3f} (n={len(other)})")
    adj = df[
        df["chla_adjusted"].notna() & (df["chla_adjusted"] > 0) & (df["chl_bing"] > 0)
    ]
    if not adj.empty:
        rd_adj = rel_diff(adj["chl_bing"], adj["chla_adjusted"])
        lines.append(
            f"vs. adjusted Argo: median = {np.median(rd_adj):+.3f} (n={len(adj)}, "
            f"vs. raw median on same n = {adj['rel_diff'].median():+.3f})"
        )
    return "\n".join(lines)


def main(argv=None):
    args = _parse_args(argv)
    args.outdir.mkdir(parents=True, exist_ok=True)

    df = load_chl_matchups(args.db)
    print(f"Loaded {len(df)} total matchups with a BING fit")
    v = valid_chl(df, clip=1.5)
    print(
        f"{len(v)} valid (finite, positive chl_bing & chla_argo, |rel_diff| <= 1.5)\n"
    )
    print("=== Headline Chl-a bias summary ===")
    print(_summary(v))
    print()

    plot_chl_scatter.plot_chl_scatter(
        v, outfile=args.outdir / "chl_pace_vs_argo_scatter.png", dpi=args.dpi
    )
    plot_chl_histogram.plot_chl_histogram(
        v, outfile=args.outdir / "chl_reldiff_histogram.png", dpi=args.dpi
    )
    plot_chl_maps.plot_static_map(
        v, outfile=args.outdir / "chl_global_map.png", dpi=args.dpi
    )
    plot_chl_maps.plot_interactive_map(v, outfile=args.outdir / "chl_global_map.html")

    plot_chl_stratification.plot_vs_geometry(
        v,
        "dtime_hours",
        "Time separation Δt (hours)",
        outfile=args.outdir / "chl_reldiff_vs_dtime.png",
        dpi=args.dpi,
    )
    plot_chl_stratification.plot_vs_geometry(
        v,
        "distance_km",
        "Spatial separation (km)",
        outfile=args.outdir / "chl_reldiff_vs_dist.png",
        dpi=args.dpi,
    )
    plot_chl_stratification.plot_vs_mld(
        v, outfile=args.outdir / "chl_reldiff_vs_mld.png", dpi=args.dpi
    )
    plot_chl_stratification.plot_seasonal(
        v, outfile=args.outdir / "chl_reldiff_seasonal.png", dpi=args.dpi
    )
    plot_chl_stratification.plot_by_basin(
        v, outfile=args.outdir / "chl_reldiff_by_basin.png", dpi=args.dpi
    )

    plot_chl_quality.plot_quality_subset(
        v,
        cc_thresh=50.0,
        chisq_thresh=1.2,
        outfile=args.outdir / "chl_reldiff_quality_subset.png",
        dpi=args.dpi,
    )
    plot_chl_quality.plot_by_data_mode(
        v, outfile=args.outdir / "chl_reldiff_by_data_mode.png", dpi=args.dpi
    )

    plot_chl_diagnostics.plot_vs_magnitude(
        v, outfile=args.outdir / "chl_reldiff_vs_magnitude.png", dpi=args.dpi
    )
    plot_chl_diagnostics.plot_vs_bbp_bias(
        v, outfile=args.outdir / "chl_bias_vs_bbp_bias.png", dpi=args.dpi
    )
    plot_chl_diagnostics.plot_vs_adg(
        v, outfile=args.outdir / "chl_reldiff_vs_adg.png", dpi=args.dpi
    )

    plot_chl_adjusted.plot_raw_vs_adjusted(
        v, outfile=args.outdir / "chl_raw_vs_adjusted_argo.png", dpi=args.dpi
    )
    plot_chl_adjusted.plot_bias_raw_vs_adjusted(
        v, outfile=args.outdir / "chl_bias_raw_vs_adjusted.png", dpi=args.dpi
    )

    plot_chl_dac.plot_by_dac(
        v, outfile=args.outdir / "chl_reldiff_by_dac_aoml.png", dpi=args.dpi
    )
    plot_chl_dac.plot_by_project(
        v, outfile=args.outdir / "chl_reldiff_by_dac_all.png", dpi=args.dpi
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
