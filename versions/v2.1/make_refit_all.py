"""v2.1 Task 3 selection: every matchup with a BING 2.0 fit whose chain NPZ
exists (Plan §4, V3), written to ``versions/v2.1/refit_all.csv``.

    python versions/v2.1/make_refit_all.py --db $PAB_DATA_DIR/v2/pab.db \
        --chains $PAB_DATA_DIR/v2/fit_chains

Read-only on the DB. Also lists the matchups with no 2.0 fit (for the
write-up) and fails if any 2.0 NPZ is missing.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--chains", required=True)
    ap.add_argument("--out", default=str(HERE / "refit_all.csv"))
    a = ap.parse_args(argv)
    c = sqlite3.connect(f"file:{Path(a.db).resolve()}?mode=ro", uri=True)
    rows = c.execute(
        "SELECT f.matchup_id, f.fit_id, p.ix, p.iy FROM fits f "
        "JOIN matchup_pixels p ON p.pixel_id = f.pixel_id "
        "WHERE f.algorithm='BING' AND f.pab_version='2.0' ORDER BY f.matchup_id"
    ).fetchall()
    chains = Path(a.chains)
    missing = [r[1] for r in rows if not (chains / f"{r[1]}.npz").is_file()]
    if len({r[0] for r in rows}) != len(rows):
        print("more than one 2.0 fit per matchup", file=sys.stderr)
        return 1
    no_fit = [m for (m,) in c.execute(
        "SELECT matchup_id FROM matchups WHERE matchup_id NOT IN "
        "(SELECT matchup_id FROM fits WHERE algorithm='BING' AND pab_version='2.0') "
        "ORDER BY matchup_id")]
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["matchup_id", "fit_id_v2_0", "ix", "iy"])
        w.writerows(rows)
    print(f"{len(rows)} matchups -> {a.out}; 2.0 NPZ missing: {len(missing)}")
    print(f"{len(no_fit)} matchups with no 2.0 fit (not re-fitted):", *no_fit, sep="\n  ")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
