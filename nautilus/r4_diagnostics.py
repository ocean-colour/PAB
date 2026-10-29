"""Prompt 7 Task 4 — R4 red-edge diagnostics on the Prompt 6 slice's 100 matchups.

Reports the OBSERVED Rrs and Rrs_unc at 685 / 713 / 719 nm. 713 and 719 are
**outside** the 400-700 fit window (JXP moved `wave_max` there after Prompt 3
found Rrs(719) negative on 6 of 20 matchups and noise-dominated on 2 more), so
these are diagnostics on excluded bands, not fit residuals. The question is
whether excluding the red edge was right -- which the observations answer on
their own, without reconstructing a model beyond where it was fitted.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import statistics as st
import warnings

warnings.simplefilter("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

import numpy as np  # noqa: E402

from pab.matchup.engine import _open_with_timeout  # noqa: E402
from pab.pace import extract as _extract  # noqa: E402

DB = "/mnt/tank/Oceanography/data/Color/PAB/v2/pab.db"
SLICE = "/mnt/tank/Oceanography/data/Color/PAB/v2/slice_100.csv"
OUT = "/mnt/tank/Oceanography/data/Color/PAB/v2/logs/r4_diagnostics.csv"
BANDS = (685, 713, 719)


def main() -> None:
    want = {r["matchup_id"] for r in csv.DictReader(open(SLICE))}
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = [
        r
        for r in c.execute(
            "SELECT m.matchup_id, g.data_url, px.ix, px.iy "
            "FROM matchups m JOIN granules g ON g.granule_id=m.granule_id "
            "JOIN matchup_pixels px ON px.matchup_id=m.matchup_id AND px.rank=1 "
            "WHERE g.data_url IS NOT NULL"
        )
        if r[0] in want
    ]
    print(f"slice matchups with a granule url: {len(rows)}", flush=True)

    out, failed = [], 0
    for i, (mid, url, ix, iy) in enumerate(rows, 1):
        try:
            ds = _open_with_timeout(url, timeout_s=90)
            wave, rrs, unc = _extract.extract_spectrum(ds, ix, iy)
            try:
                ds.close()
            except Exception:
                pass
        except Exception as e:
            failed += 1
            print(f"  [{i}] FAILED {type(e).__name__}: {str(e)[:50]}", flush=True)
            continue
        w = np.asarray(wave)
        rec = {"matchup_id": mid}
        for b in BANDS:
            j = int(np.argmin(np.abs(w - b)))
            r_, u_ = float(rrs[j]), float(unc[j]) if unc is not None else float("nan")
            rec[f"rrs{b}"] = r_
            rec[f"unc{b}"] = u_
            rec[f"ratio{b}"] = (u_ / r_) if r_ not in (0.0,) and np.isfinite(r_) else float("nan")
        out.append(rec)
        if i % 5 == 0:
            print(f"  [{i}/{len(rows)}] ok={len(out)} failed={failed}", flush=True)

    with open(OUT, "w", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        wtr.writeheader()
        wtr.writerows(out)
    print(f"\nwrote {OUT}  ({len(out)} matchups, {failed} failed)\n")

    print("=== R4: is the red edge usable? ===")
    for b in BANDS:
        vals = [r[f"rrs{b}"] for r in out if np.isfinite(r[f"rrs{b}"])]
        rats = [r[f"ratio{b}"] for r in out if np.isfinite(r[f"ratio{b}"])]
        neg = sum(1 for v in vals if v < 0)
        noisy = sum(1 for x in rats if x > 1.0)
        bad = sum(
            1
            for r in out
            if (r[f"rrs{b}"] < 0) or (np.isfinite(r[f"ratio{b}"]) and r[f"ratio{b}"] > 1.0)
        )
        print(
            f"  {b} nm  median Rrs {st.median(vals): .3e}   "
            f"median unc/Rrs {st.median(rats):5.2f}   "
            f"negative {neg:3d}/{len(vals)}   "
            f"unc>signal {noisy:3d}/{len(rats)}   "
            f"UNUSABLE {bad:3d}/{len(out)} ({bad / len(out) * 100:.0f} %)"
        )
    print("\n  (400-700 is the fit window; 713/719 are outside it by design)")


if __name__ == "__main__":
    main()
