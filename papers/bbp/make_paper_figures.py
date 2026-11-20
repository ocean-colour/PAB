"""
Generate the paper figures for the PACE–Argo bbp700 matchup paper.

``--db`` is the release switch: every figure is built from that database and
from the ``matchup_summary.parquet`` that sits next to it (both are published
together under ``s3://pab/<version>/``). Re-rendering for a new release is a
matter of pointing ``--db`` at the new file. The default is the v2.1 release,
``$PAB_DATA_DIR/v2/pab.db`` (it also holds the superseded 2.0 / 2.0.1 rows; the
gatherers report the newest version family, 2.1).

Usage:
    python papers/bbp/make_paper_figures.py
    python papers/bbp/make_paper_figures.py --which scatter histogram seasonal
    python papers/bbp/make_paper_figures.py --skip maps
    python papers/bbp/make_paper_figures.py --db /path/to/other_release/pab.db
    python papers/bbp/make_paper_figures.py --out-dir ~/Desktop/paper_figs/

Available figure groups (inputs in brackets):
    scatter      1:1 bbp700 scatter with stats                  [db]
    histogram    distribution of δ                              [db]
    geometry     δ vs matchup Δt and vs distance                [db]
    basin        basin comparison                               [db]
    mld          δ vs mixed layer depth                         [db]
    seasonal     seasonal cycle by hemisphere                   [db]
    delta_bbp    δ vs PACE / Argo bbp (both normalizations)     [parquet]
    rrs700       BING Rrs(700) vs δ colored by time             [db, parquet]
    chl          Chl-a 1:1 scatter                              [db]
    giop         BING vs GIOP three-panel comparison            [db, parquet]
    outliers     outlier case study                             [db, parquet]
    maps         cartopy global maps (needs cartopy)            [db, parquet]

The script exits non-zero if any requested group fails.
"""
import argparse
import sys
import traceback
from pathlib import Path

from pab.config import DATA_DIR

#: Default database: the v2.1 release (s3://pab/v2/pab.db; 2.1 published in place
#: under v2/, build_v2_1_rerun.md V1 = A, V10).
DEFAULT_DB = Path(DATA_DIR) / "v2" / "pab.db"
PARQUET_NAME = "matchup_summary.parquet"

#: Paper-figure group -> keys of ``make_analysis_figures.FIGURES``.
ANALYSIS_GROUPS = {
    "scatter":   ["scatter"],
    "histogram": ["histogram"],
    "geometry":  ["dtime", "dist"],
    "basin":     ["basin"],
    "mld":       ["mld"],
    "seasonal":  ["seasonal"],
}

#: Inputs each group reads; only these are required to exist.
NEEDS = {
    **{g: {"db"} for g in ANALYSIS_GROUPS},
    "delta_bbp": {"parquet"},
    "rrs700":    {"db", "parquet"},
    "chl":       {"db"},
    "giop":      {"db", "parquet"},
    "outliers":  {"db", "parquet"},
    "maps":      {"db", "parquet"},
}

ALL_GROUPS = list(NEEDS)


# ── figure groups ─────────────────────────────────────────────────────────────

def run_analysis_figures(groups, db, parquet, out_dir):
    """Figures from pab/matchup/make_analysis_figures.py (loaded once)."""
    from pab.matchup import make_analysis_figures as maf

    keys = [k for g in ALL_GROUPS if g in groups for k in ANALYSIS_GROUPS.get(g, [])]
    print(f"\n── Analysis figures: {keys} ──")
    df = maf._load(db)
    print(f"   Loaded {len(df):,} valid matchups, {df['wmo'].nunique()} floats "
          f"(pab_version: {dict(df['pab_version'].value_counts())})")
    for key in keys:
        fn, fname = maf.FIGURES[key]
        fn(df, out_dir / fname)
        print(f"   ✓ {fname}")


def run_delta_bbp(db, parquet, out_dir):
    print("\n── δ vs bbp figures ──")
    from pab.matchup.plot_delta_vs_bbp import load_data, plot_pace_normalized, plot_argo_normalized
    df = load_data(parquet=str(parquet))
    print(f"   Loaded {len(df):,} matchups")
    plot_pace_normalized(df, out=str(out_dir))
    plot_argo_normalized(df, out=str(out_dir))


def run_rrs700(db, parquet, out_dir):
    print("\n── BING Rrs(700) vs δ ──")
    from pab.matchup.plot_rrs700_vs_delta import load_data, make_figure
    df = load_data(db=str(db), parquet=str(parquet))
    print(f"   Loaded {len(df):,} matchups with anw700")
    make_figure(df, out=str(out_dir / "rrs700_vs_delta.png"))


def run_chl(db, parquet, out_dir):
    print("\n── Chl-a scatter ──")
    from pab.matchup.chl.data import load_chl_matchups, valid_chl
    from pab.matchup.chl.plot_chl_scatter import plot_chl_scatter
    df = valid_chl(load_chl_matchups(db))
    print(f"   Loaded {len(df):,} valid Chl-a matchups")
    plot_chl_scatter(df, outfile=out_dir / "chl_pace_vs_argo_scatter.png")


def run_giop(db, parquet, out_dir):
    print("\n── BING vs GIOP comparison ──")
    from pab.matchup.plot_bing_giop_comparison import load_data, make_figure
    df = load_data(db=str(db), parquet=str(parquet))
    print(f"   Loaded {len(df):,} matched BING+GIOP matchups")
    make_figure(df, out=str(out_dir / "bing_giop_comparison.png"))


def run_outliers(db, parquet, out_dir):
    print("\n── Outlier case study ──")
    from pab.matchup.plot_outlier_cases import load_data, make_figure
    df, worst, normal = load_data(db=str(db), parquet=str(parquet))
    print(f"   {len(df):,} total matchups, {len(worst)} outlier cases")
    make_figure(df, worst, normal, out=str(out_dir / "outlier_cases.png"))


def run_maps(db, parquet, out_dir):
    """Cartopy maps from papers/bbp/plot_global_maps.py (next to this script)."""
    print("\n── Cartopy global maps ──")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import plot_global_maps as pgm  # raises ImportError without cartopy
    par, d, o = str(parquet), str(db), str(out_dir)
    pgm.plot_bing_global(par, o)
    pgm.plot_giop_global(par, d, o)
    pgm._plot_strict(par, d, "GIOP", "delta", "Strict GIOP",
                     "fig15_strict_map_giop.png", o)
    pgm._plot_strict(par, d, "BING", "delta", "Strict BING",
                     "fig_strict_map_bing.png", o)


RUNNERS = {
    "delta_bbp": run_delta_bbp,
    "rrs700":    run_rrs700,
    "chl":       run_chl,
    "giop":      run_giop,
    "outliers":  run_outliers,
    "maps":      run_maps,
}


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help=f"PAB database; selects the release (default: {DEFAULT_DB})")
    parser.add_argument("--parquet", type=Path, default=None,
                        help=f"Matchup summary (default: {PARQUET_NAME} next to --db)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Directory for the figures (default: paper_figures/ next to --db)")
    parser.add_argument("--which", nargs="+", choices=ALL_GROUPS, default=None,
                        help="Subset of figure groups to generate (default: all)")
    parser.add_argument("--skip", nargs="+", choices=ALL_GROUPS, default=None,
                        help="Figure groups to skip")
    args = parser.parse_args()

    db = args.db.expanduser()
    parquet = (args.parquet or db.parent / PARQUET_NAME).expanduser()
    out_dir = (args.out_dir or db.parent / "paper_figures").expanduser()

    groups = set(args.which or ALL_GROUPS) - set(args.skip or [])
    groups = [g for g in ALL_GROUPS if g in groups]          # stable order

    print(f"Database:         {db}")
    print(f"Parquet:          {parquet}")
    print(f"Output directory: {out_dir}")
    print(f"Figure groups:    {groups}")

    # Check inputs before creating anything; only the files a group reads are required.
    paths = {"db": db, "parquet": parquet}
    missing = {k for g in groups for k in NEEDS[g] if not paths[k].exists()}
    if missing:
        for k in sorted(missing):
            users = [g for g in groups if k in NEEDS[g]]
            print(f"ERROR: {k} not found at {paths[k]} (needed by: {', '.join(users)})")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    failed = []
    analysis = [g for g in groups if g in ANALYSIS_GROUPS]
    if analysis:
        try:
            run_analysis_figures(analysis, db, parquet, out_dir)
        except Exception:
            traceback.print_exc()
            failed.extend(analysis)

    for g in groups:
        if g in RUNNERS:
            try:
                RUNNERS[g](db, parquet, out_dir)
            except Exception:
                traceback.print_exc()
                failed.append(g)

    if failed:
        print(f"\nFAILED groups: {failed}")
        sys.exit(1)
    print("\nDone.")


if __name__ == "__main__":
    main()
