"""Gate checks for the pab:2.0.0 in-pod validation (v2_validate_job.yaml).

Exits non-zero with a named failure rather than printing a wall of numbers:
the job should go red when 2.0 is wrong, not require someone to read the log.
"""

import json
import sys
from pathlib import Path

import numpy as np

db_path, data_dir = sys.argv[1], Path(sys.argv[2])
failures = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' — ' + str(detail)) if detail else ''}")
    if not ok:
        failures.append(name)


import sqlite3  # noqa: E402

c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
q = c.execute

counts = {
    t: q(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    for t in ("profiles", "granules", "matchups", "matchup_pixels", "fits", "fit_results")
}
print("counts:", counts)
check("schema is v5", q("PRAGMA user_version").fetchone()[0] == 5)
check("matchups exist", counts["matchups"] > 0, counts["matchups"])
check("fits exist", counts["fits"] > 0, counts["fits"])

# --- geometry stage ---------------------------------------------------------
px_total = counts["matchup_pixels"]
px_geom = q("SELECT COUNT(*) FROM matchup_pixels WHERE theta_s IS NOT NULL").fetchone()[0]
check("every pixel has geometry", px_total > 0 and px_geom == px_total, f"{px_geom}/{px_total}")
srcs = [r[0] for r in q("SELECT DISTINCT geom_source FROM matchup_pixels WHERE theta_s IS NOT NULL")]
check("geom_source is L1B_V3", srcs == ["L1B_V3"], srcs)
rng = q(
    "SELECT MIN(theta_s), MAX(theta_s), MIN(theta_v), MAX(theta_v), MIN(dphi), MAX(dphi) "
    "FROM matchup_pixels WHERE theta_s IS NOT NULL"
).fetchone()
if px_geom:
    print(f"  geometry ranges: theta_s {rng[0]:.2f}..{rng[1]:.2f}  "
          f"theta_v {rng[2]:.2f}..{rng[3]:.2f}  dphi {rng[4]:.2f}..{rng[5]:.2f}")
    check("theta_s physical", 0 <= rng[0] and rng[1] < 90)
    check("theta_v physical", 0 <= rng[2] and rng[3] <= 70)
    check("dphi wrapped to (-180, 180]", -180 < rng[4] and rng[5] <= 180)

# --- fit stage: the schema-v5 RT columns ------------------------------------
bing = q("SELECT * FROM fits WHERE algorithm = 'BING'").fetchall()
check("BING fits written", len(bing) > 0, len(bing))
expected = {
    "rt_backend": "robust_hybrid", "include_raman": 1, "include_chl_fl": 1,
    "include_cdom_fl": 0, "fit_bp": 1, "phi_c": 0.02,
    "wave_max": 700.0,  # Q2: 2.0 moved back from 720 to 700 nm
    "pab_version": "2.0",
}
for col, want in expected.items():
    got = sorted({r[col] for r in bing})
    check(f"fits.{col} == {want!r}", got == [want], got)
ids_ok = all(r["fit_id"].endswith("_v2.0") for r in bing)
check("fit_id is version-aware (_v2.0)", ids_ok, bing[0]["fit_id"] if bing else "")

# --- provenance -------------------------------------------------------------
pkg = json.loads(bing[0]["pkg_versions"]) if bing else {}
check("pkg_versions has robust", pkg.get("robust", "not installed") != "not installed",
      pkg.get("robust"))
shas = pkg.get("git_sha", {})
check("git_sha has all five repos", len(shas) == 5, sorted(shas))
unknown = [k for k, v in shas.items() if v == "unknown"]
check("no git_sha is 'unknown' (PAB_GIT_SHAS reached the process)", not unknown, unknown or shas)

# --- numeric sanity ---------------------------------------------------------
def vals(suffix):
    return [r[0] for r in q(
        "SELECT value FROM fit_results WHERE quantity LIKE ? AND value IS NOT NULL",
        (f"%{suffix}",))]

bbp, bp = vals("bbp700"), vals("_Bp")
if bbp:
    print(f"  bbp700: {min(bbp):.3e}..{max(bbp):.3e}")
    check("bbp700 in 1e-5..1e-2", 1e-5 <= min(bbp) and max(bbp) <= 1e-2)
if bp:
    print(f"  Bp: {min(bp):.4f}..{max(bp):.4f}")
    check("Bp inside its prior [0.004, 0.05]", 0.004 <= min(bp) and max(bp) <= 0.05)
chisq = [r[0] for r in q("SELECT chisq FROM fits WHERE algorithm='BING' AND chisq IS NOT NULL")]
acc = [r[0] for r in q("SELECT accept_frac FROM fits WHERE algorithm='BING' AND accept_frac IS NOT NULL")]
if chisq:
    print(f"  chisq: {min(chisq):.2f}..{max(chisq):.2f}")
    check("chisq order-unity (< 20)", max(chisq) < 20)
if acc:
    print(f"  accept_frac: {min(acc):.3f}..{max(acc):.3f}")
    check("acceptance 0.05..0.7", 0.05 <= min(acc) and max(acc) <= 0.7)

# --- chains -----------------------------------------------------------------
chains_dir = data_dir / "fit_chains"
npz = sorted(chains_dir.glob("*.npz"))
check(f"chains under {chains_dir}", len(npz) > 0, len(npz))
if npz:
    with np.load(npz[0]) as z:
        shape = z["chains"].shape
    mb = npz[0].stat().st_size / 1e6
    print(f"  chains[0]: {npz[0].name}  shape {shape}  {mb:.2f} MB")
    check("chains have 6 columns (free B_p)", shape[-1] == 6, shape)
    check("chain filename is version-aware", npz[0].name.endswith("_v2.0.npz"))

# --- figures ----------------------------------------------------------------
# Added after the first in-pod run: the gates reported ALL PASSED while the
# `figure` stage had failed for every fit. A gate set that only looks at the
# database cannot see a stage that produced nothing, so check the artefact.
figs = sorted((data_dir / "pipeline" / "figures").glob("*.png"))
fit_figs = [f for f in figs if not f.name.endswith("_scene.png")]
check("fit figures rendered", len(fit_figs) >= len(bing), f"{len(fit_figs)} for {len(bing)} fits")
recorded = q("SELECT COUNT(*) FROM fits WHERE algorithm='BING' AND figure_path IS NOT NULL").fetchone()[0]
check("fits.figure_path recorded", recorded == len(bing), f"{recorded}/{len(bing)}")

c.close()
print()
if failures:
    print(f"GATES FAILED ({len(failures)}): {failures}")
    sys.exit(1)
print("ALL GATES PASSED")
