"""Build the v2.1 gate selections (build_v2_1_rerun.md Plan §3, Task 2).

* ``slice_200.csv``: 200 matchups, 50 per θ_v band (<25, 25–35, 35–45,
  >45°), each band spread over ocean basin × season by round-robin over the
  (basin, season) cells. 10 of the 51 2.0.1 re-fits are forced in, placed by
  their own θ_v band.
* ``bp_arm_50.csv``: 50 of the 200 for the fixed-``B_p`` arm. 12–13 per band,
  ``success = 1`` 2.0 fits only, no 2.0.1 re-fits, evenly spaced in θ_s
  within each band.

The 50 ``ztt_slice`` ordinary fits (Plan §3 asked to re-use them) cannot be
reconstructed: their 300-fit sample list and the run's ``specs.json`` lived
in ``/tmp`` and were lost. That is noted in the log.

Reads the v2 DB **read-only** (``mode=ro``). Deterministic (seed 2110).

    python versions/v2.1/make_slice.py $PAB_DATA_DIR/v2/pab.db $PAB_DATA_DIR/v2/fit_chains
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

SEED = 2110
N_BAND = 50
N_REFIT = 10
N_ARM = 50
BANDS = ((0, 25), (25, 35), (35, 45), (45, 90))
OUT = Path(__file__).resolve().parent


def band_of(theta_v: float) -> int:
    for k, (lo, hi) in enumerate(BANDS):
        if lo <= theta_v < hi:
            return k + 1
    raise ValueError(theta_v)


def basin(lat: float, lon: float) -> str:
    """Coarse basin label, for spreading the selection (not science)."""
    lon = ((lon + 180) % 360) - 180
    if lat < -45:
        return "Southern"
    if lat > 66:
        return "Arctic"
    if 30 <= lat <= 46 and -6 <= lon <= 37:
        return "Med"
    if 53 <= lat <= 66 and 9 <= lon <= 31:
        return "Baltic"
    if 20 <= lon < 120 and lat < 30:
        return "Indian"
    if -70 <= lon < 20:
        return "Atlantic"
    return "Pacific"


def season(lat: float, time: str) -> str:
    month = int(time[5:7])
    s = ("DJF", "DJF", "MAM", "MAM", "MAM", "JJA", "JJA", "JJA", "SON", "SON",
         "SON", "DJF")[month - 1]
    if lat < 0:  # austral: flip so the label means the physical season
        s = {"DJF": "JJA", "JJA": "DJF", "MAM": "SON", "SON": "MAM"}[s]
    return s


def main(db: str, chains: str) -> None:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT f.matchup_id, f.fit_id, f.success, p.ix, p.iy,
               p.theta_s, p.theta_v, p.dphi,
               COALESCE(p.latitude, pr.latitude) AS latitude,
               COALESCE(p.longitude, pr.longitude) AS longitude,
               COALESCE(pr.time, gr.time_start) AS time,
               r.value AS bbp700,
               (SELECT COUNT(*) FROM fits g WHERE g.matchup_id = f.matchup_id
                  AND g.pixel_id = f.pixel_id AND g.pab_version = '2.0.1') AS refit
        FROM fits f
        JOIN matchup_pixels p ON p.pixel_id = f.pixel_id
        JOIN matchups m ON m.matchup_id = f.matchup_id
        JOIN profiles pr ON pr.profile_id = m.profile_id
        LEFT JOIN granules gr ON gr.granule_id = m.granule_id
        LEFT JOIN fit_results r ON r.fit_id = f.fit_id
             AND r.quantity = 'BING_ExpBPow_bbp700'
        WHERE f.algorithm = 'BING' AND f.pab_version = '2.0'
          AND p.theta_v IS NOT NULL
        ORDER BY f.fit_id
        """
    ).fetchall()
    conn.close()
    pool = []
    for r in rows:
        d = dict(r)
        if not (Path(chains) / f"{d['fit_id']}.npz").is_file():
            continue
        d["band"] = band_of(d["theta_v"])
        d["basin"] = basin(d["latitude"], d["longitude"])
        d["season"] = season(d["latitude"], d["time"])
        pool.append(d)
    rng = np.random.default_rng(SEED)

    refits = [d for d in pool if d["refit"]]
    forced = [refits[i] for i in sorted(rng.choice(len(refits), N_REFIT, replace=False))]
    chosen = {d["fit_id"]: d for d in forced}

    for band in range(1, 5):
        have = [d for d in chosen.values() if d["band"] == band]
        cells = defaultdict(list)
        for d in pool:
            if d["band"] == band and d["fit_id"] not in chosen and not d["refit"]:
                cells[(d["basin"], d["season"])].append(d)
        for c in cells.values():
            rng.shuffle(c)
        keys = sorted(cells)
        rng.shuffle(keys)
        need = N_BAND - len(have)
        while need > 0:
            progressed = False
            for k in keys:
                if need and cells[k]:
                    d = cells[k].pop()
                    chosen[d["fit_id"]] = d
                    need -= 1
                    progressed = True
            if not progressed:
                raise RuntimeError(f"band {band}: pool exhausted")

    sel = sorted(chosen.values(), key=lambda d: (d["band"], d["fit_id"]))
    assert len(sel) == 4 * N_BAND and len({d["matchup_id"] for d in sel}) == len(sel)
    cols = ["matchup_id", "fit_id", "ix", "iy", "band", "theta_s", "theta_v",
            "dphi", "latitude", "longitude", "time", "basin", "season", "success",
            "refit", "bbp700"]
    with open(OUT / "slice_200.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sel)

    arm = []
    per_band = [13, 13, 12, 12]
    for band, k in zip(range(1, 5), per_band, strict=True):
        c = sorted((d for d in sel if d["band"] == band and d["success"] == 1
                    and not d["refit"]), key=lambda d: d["theta_s"])
        idx = np.unique(np.round(np.linspace(0, len(c) - 1, k)).astype(int))
        arm += [c[i] for i in idx]
    assert len(arm) == N_ARM, len(arm)
    with open(OUT / "bp_arm_50.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(arm)

    def tab(xs, key):
        out = defaultdict(int)
        for d in xs:
            out[d[key]] += 1
        return dict(sorted(out.items()))

    print("slice:", len(sel), "bands", tab(sel, "band"), "refits", sum(d["refit"] for d in sel))
    print("  basins", tab(sel, "basin"))
    print("  seasons", tab(sel, "season"))
    print("  theta_s range", min(d["theta_s"] for d in sel), max(d["theta_s"] for d in sel))
    print("arm:", len(arm), "bands", tab(arm, "band"), "basins", tab(arm, "basin"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
