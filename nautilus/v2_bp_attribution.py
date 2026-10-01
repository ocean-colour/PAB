"""Prompt 6 Task 3 — attribution diagnostic: how much of the `bbp700` shift is the free `B_p`?

Refits the leading slice's 100 matchups with ``fit_Bp=False`` (``Bp_value=0.01``),
otherwise the 2.0 configuration, so the difference against the slice's
free-``B_p`` fits isolates what sampling ``B_p`` contributes versus what the
emulator + inelastic terms contribute on their own.

**This never touches the v2 database or its chains.** It runs against a scratch
copy and writes chains under ``PAB_DATA_DIR=/scratch``, because:

* ``make_fit_id`` is ``{matchup}_{ix}_{iy}_{model_pair}_v{version}`` and does
  **not** encode ``fit_Bp``. A B_p-fixed fit therefore has the *same* fit_id as
  the free-B_p fit already stored, so it would be skipped as "already done" —
  and ``replace=True`` against the real store would **overwrite the real 2.0
  fits with diagnostic ones**. On a scratch copy that is harmless and is the
  only way to get the comparison.

Mounted via ConfigMap, following `coverage_check.py` / `v2_ingest_failures.py`.
"""

from __future__ import annotations

import csv
import logging
import os
import sqlite3
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
_log = logging.getLogger("bp_attribution")

SCRATCH_DB = os.environ.get("SCRATCH_DB", "/scratch/pab_bpfix.db")
SLICE_CSV = os.environ.get("SLICE_CSV", "/data/v2/slice_100.csv")
OUT_CSV = os.environ.get("OUT_CSV", "/data/v2/bp_attribution.csv")
JOBS = int(os.environ.get("JOBS", "32"))
QTY = "BING_ExpBPow_bbp700"


def main() -> int:
    from pab.db.store import Store
    from pab.fit.models import FitConfig
    from pab.fit.run import build_fits

    if not SCRATCH_DB.startswith("/scratch"):
        _log.error("refusing to run: SCRATCH_DB=%r is not under /scratch", SCRATCH_DB)
        return 2
    if os.environ.get("PAB_DATA_DIR", "").startswith("/data/v2"):
        _log.error("refusing to run: PAB_DATA_DIR points at v2; chains would land there")
        return 2

    sel = {r["matchup_id"] for r in csv.DictReader(open(SLICE_CSV))}
    _log.info("slice: %d matchups", len(sel))

    cfg = FitConfig(fit_Bp=False)  # Bp_value defaults to 0.01, as Task 3 specifies
    _log.info(
        "config: rt_backend=%s fit_Bp=%s Bp_value=%s Raman=%s Chl_fl=%s wave=%s-%s",
        cfg.rt_backend, cfg.fit_Bp, cfg.Bp_value,
        cfg.include_Raman, cfg.include_Chl_fl, cfg.wave_min, cfg.wave_max,
    )

    with Store.open(SCRATCH_DB, create=False) as store:
        out = build_fits(
            store,
            config=cfg,
            jobs=JOBS,
            selection=sel,
            replace=True,  # safe ONLY because this is a scratch copy -- see module docstring
        )
    _log.info(
        "bp-fixed fits: %d written, %d failed", len(out["written"]), len(out["failed"])
    )

    # Export bbp700 for the comparison. The free-B_p values come from the real
    # v2 store (read-only) so the pairing is explicit rather than implied.
    c = sqlite3.connect(f"file:{SCRATCH_DB}?mode=ro", uri=True)
    fixed = {
        r[0]: r[1]
        for r in c.execute(
            "SELECT f.matchup_id, fr.value FROM fits f JOIN fit_results fr "
            "ON fr.fit_id = f.fit_id WHERE fr.quantity = ? AND f.rt_backend LIKE 'robust%'",
            (QTY,),
        )
    }
    v2 = sqlite3.connect("file:/data/v2/pab.db?mode=ro", uri=True)
    free = {
        r[0]: r[1]
        for r in v2.execute(
            "SELECT f.matchup_id, fr.value FROM fits f JOIN fit_results fr "
            "ON fr.fit_id = f.fit_id WHERE fr.quantity = ? AND f.rt_backend LIKE 'robust%'",
            (QTY,),
        )
    }
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["matchup_id", "bbp700_free_Bp", "bbp700_fixed_Bp"])
        n = 0
        for m in sorted(set(fixed) & set(free) & sel):
            w.writerow([m, free[m], fixed[m]])
            n += 1
    _log.info("wrote %s (%d paired matchups)", OUT_CSV, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
