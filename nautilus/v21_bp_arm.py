"""The v2.1 fixed-``B_p`` arm driver (build_v2_1_rerun.md Plan §3, T1-Q1).

Fits a selection of matchups with ``B_p`` **fixed** at ``--bp`` in one
geometry mode, replaying each pixel's 2.0 spectrum from its chain NPZ. Run it
once with ``--geometry-mode normalized`` (arm-N) and once with ``observed``
(arm-O) on **separate DB copies and separate** ``--data-dir``: both passes
mint the same ``…_v<pab_version>`` ``fit_id``, and the chain NPZs are named by
it. ``fits.geom_mode`` and ``fits.fit_bp`` tell the rows apart.

It goes through ``pab.fit.run.build_fits(…, selection=, spectra=)``, the same
path as ``pab --stage fit --matchups-csv … --replay-chains …``. The production
CLI exposes no ``FitConfig`` fields, which is why this driver exists.

    PYTHONWARNINGS=ignore python nautilus/v21_bp_arm.py \\
        --db /scratch/arm_norm.db --data-dir /data/v2.1_slice/arm_norm \\
        --matchups-csv versions/v2.1/bp_arm_50.csv \\
        --replay-chains /data/v2/fit_chains --geometry-mode normalized \\
        --bp 0.014 --jobs 25
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys


def arm_config(geometry_mode: str, bp: float):
    """The arm's ``FitConfig``: the 2.1 (normalized) or the 2.0.1 (observed)
    configuration, with ``fit_Bp=False`` and ``Bp_value=bp``; nothing else
    differs between the two."""
    from pab.fit.models import GEOM_NORMALIZED, GEOM_OBSERVED, FitConfig

    if geometry_mode == GEOM_NORMALIZED:
        return FitConfig(fit_Bp=False, Bp_value=float(bp))
    if geometry_mode == GEOM_OBSERVED:
        return FitConfig.v2_0_1(fit_Bp=False, Bp_value=float(bp))
    raise ValueError(f"--geometry-mode must be normalized|observed, got {geometry_mode!r}")


def read_selection(path) -> set[str]:
    with open(path, newline="") as fh:
        ids = {row["matchup_id"].strip() for row in csv.DictReader(fh)}
    if not ids:
        raise ValueError(f"{path}: no matchup_id rows")
    return ids


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="v21_bp_arm", description=__doc__.split("\n")[0])
    p.add_argument("--db", required=True)
    p.add_argument("--data-dir", required=True,
                   help="PAB_DATA_DIR for this pass (its chains land in DATA_DIR/fit_chains)")
    p.add_argument("--matchups-csv", required=True)
    p.add_argument("--replay-chains", required=True)
    p.add_argument("--geometry-mode", required=True, choices=("normalized", "observed"))
    p.add_argument("--bp", type=float, default=0.014)
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    # DATA_DIR is read at `import pab`, so set it before the first import.
    os.environ["PAB_DATA_DIR"] = args.data_dir
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from pab.config import DATA_DIR, pab_version
    from pab.db import Store
    from pab.fit import run
    from pab.fit.models import prior_set_label
    from pab.fit.replay import spectrum_from_chains

    if os.path.realpath(str(DATA_DIR)) != os.path.realpath(args.data_dir):
        raise RuntimeError(f"PAB_DATA_DIR not honoured: {DATA_DIR} != {args.data_dir}")
    cfg = arm_config(args.geometry_mode, args.bp)
    sel = read_selection(args.matchups_csv)
    print(json.dumps({
        "pab_version": pab_version, "geometry_mode": cfg.geometry_mode,
        "fit_Bp": cfg.fit_Bp, "Bp_value": cfg.Bp_value,
        "prior_set": prior_set_label(cfg), "n_selection": len(sel),
        "db": args.db, "data_dir": str(DATA_DIR), "jobs": args.jobs,
    }), flush=True)
    if args.dry_run:
        return 0
    with Store.open(args.db) as store:
        out = run.build_fits(
            store, config=cfg, selection=sel, jobs=args.jobs,
            spectra=spectrum_from_chains(args.replay_chains),
        )
    print(json.dumps({k: len(v) for k, v in out.items()}), flush=True)
    if out["failed"]:
        print("failed:", *out["failed"], sep="\n  ", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
