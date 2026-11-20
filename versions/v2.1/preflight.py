"""v2.1 Task 3 custody checks: snapshot the v2 DB before the full re-fit, and
verify the returned DB against that snapshot afterwards.

    python versions/v2.1/preflight.py snapshot --db $PAB_DATA_DIR/v2/pab.db \
        --out versions/v2.1/preflight_snapshot.json
    python versions/v2.1/preflight.py verify --db <returned pab.db> \
        --snapshot versions/v2.1/preflight_snapshot.json

The DB is opened **read-only** (``mode=ro`` URI), never through ``Store.open``,
which would migrate a v5 DB to v6.

Checksums are a sha256 over the rows, ordered, of the **v5 columns only**, so
that the v6 migration (which adds ``fits.geom_mode``, NULL on legacy rows)
leaves them unchanged. Covered: every non-2.1 ``fits`` row (BING 2.0, BING
2.0.1, NASA_GIOP 1.1) and their ``fit_results``, plus ``matchups`` and
``matchup_pixels`` (which the fit stage never writes). Once 2.1 rows exist
(Task 4), also the 2.1 rows **except** ``figure_path``, so a figure render can
be checked to have written that column and nothing else.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

#: The ``fits`` columns at schema v5. 2.1 adds ``geom_mode`` (v6).
FITS_V5 = (
    "fit_id", "matchup_id", "pixel_id", "algorithm", "model_pair", "anw_model",
    "bbnw_model", "rrs_source", "prior_set", "nsteps", "nburn", "nwalkers",
    "wave_min", "wave_max", "chisq", "aic", "bic", "accept_frac", "success",
    "chains_path", "figure_path", "pkg_versions", "pab_version", "created",
    "rt_backend", "include_raman", "include_chl_fl", "include_cdom_fl", "phi_c",
    "fit_bp",
)
FIT_RESULTS = ("fit_id", "quantity", "value", "value_lo", "value_hi", "unit")
#: The legacy (algorithm, pab_version) groups that must stay byte-identical.
LEGACY = (("BING", "2.0"), ("BING", "2.0.1"), ("NASA_GIOP", "1.1"))


def connect_ro(db) -> sqlite3.Connection:
    p = Path(db).resolve()
    if not p.is_file():
        raise FileNotFoundError(p)
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def _digest(cur) -> tuple[int, str]:
    h, n = hashlib.sha256(), 0
    for row in cur:
        h.update(repr(row).encode())
        h.update(b"\n")
        n += 1
    return n, h.hexdigest()


def _cols(c, table) -> list[str]:
    return [r[1] for r in c.execute(f"PRAGMA table_info({table})")]


def snapshot(db) -> dict:
    c = connect_ro(db)
    out: dict = {"db": str(Path(db).resolve())}
    out["schema"] = c.execute("PRAGMA user_version").fetchone()[0]
    out["integrity_check"] = c.execute("PRAGMA integrity_check").fetchone()[0]
    out["fits_by_version"] = {
        f"{a}|{v}": n for a, v, n in c.execute(
            "SELECT algorithm, pab_version, COUNT(*) FROM fits GROUP BY 1, 2")}
    if "geom_mode" in _cols(c, "fits"):
        out["fits_2_1_by_geom_mode"] = {
            str(g): n for g, n in c.execute(
                "SELECT geom_mode, COUNT(*) FROM fits WHERE pab_version='2.1' GROUP BY 1")}
    fcols = ", ".join(FITS_V5)
    rcols = ", ".join("r." + k for k in FIT_RESULTS)
    groups = {}
    for alg, ver in LEGACY:
        nf, hf = _digest(c.execute(
            f"SELECT {fcols} FROM fits WHERE algorithm=? AND pab_version=? ORDER BY fit_id",
            (alg, ver)))
        nr, hr = _digest(c.execute(
            f"SELECT {rcols} FROM fit_results r JOIN fits f USING (fit_id) "
            "WHERE f.algorithm=? AND f.pab_version=? ORDER BY r.fit_id, r.quantity",
            (alg, ver)))
        groups[f"{alg}|{ver}"] = {"fits": [nf, hf], "fit_results": [nr, hr]}
    out["legacy"] = groups
    # the 2.1 rows, minus ``figure_path`` (the one column the Task 4 figure
    # render writes) and with ``geom_mode``: present once the re-fit is in
    if "geom_mode" in _cols(c, "fits"):
        cols21 = ", ".join([k for k in FITS_V5 if k != "figure_path"] + ["geom_mode"])
        nf, hf = _digest(c.execute(
            f"SELECT {cols21} FROM fits WHERE algorithm='BING' AND pab_version='2.1' "
            "ORDER BY fit_id"))
        nr, hr = _digest(c.execute(
            f"SELECT {rcols} FROM fit_results r JOIN fits f USING (fit_id) "
            "WHERE f.algorithm='BING' AND f.pab_version='2.1' ORDER BY r.fit_id, r.quantity"))
        out["v2_1_nofig"] = {"fits": [nf, hf], "fit_results": [nr, hr]}
        out["v2_1_figure_path"] = c.execute(
            "SELECT COUNT(figure_path) FROM fits WHERE pab_version='2.1'").fetchone()[0]
    for t in ("matchups", "matchup_pixels"):
        cols = ", ".join(_cols(c, t))
        out[t] = list(_digest(c.execute(f"SELECT {cols} FROM {t} ORDER BY rowid")))
    c.close()
    return out


def verify(db, snap: dict) -> list[str]:
    """Return a list of problems; empty means the returned DB passes Plan §4."""
    now = snapshot(db)
    bad = []
    if now["integrity_check"] != "ok":
        bad.append(f"integrity_check: {now['integrity_check']}")
    if now["schema"] != 6:
        bad.append(f"schema {now['schema']} != 6")
    for k, v in snap["legacy"].items():
        if now["legacy"].get(k) != v:
            bad.append(f"legacy rows changed: {k}: {now['legacy'].get(k)} != {v}")
    if "v2_1_nofig" in snap and now.get("v2_1_nofig") != snap["v2_1_nofig"]:
        bad.append(f"2.1 rows changed beyond figure_path: {now.get('v2_1_nofig')} "
                   f"!= {snap['v2_1_nofig']}")
    for t in ("matchups", "matchup_pixels"):
        if now[t] != snap[t]:
            bad.append(f"{t} changed: {now[t]} != {snap[t]}")
    modes = now.get("fits_2_1_by_geom_mode", {})
    if set(modes) - {"normalized"}:
        bad.append(f"2.1 rows with a geom_mode other than normalized: {modes}")
    now["problems"] = bad
    return now


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--db", required=True)
    s.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--db", required=True)
    v.add_argument("--snapshot", required=True)
    v.add_argument("--out")
    a = ap.parse_args(argv)
    if a.cmd == "snapshot":
        snap = snapshot(a.db)
        Path(a.out).write_text(json.dumps(snap, indent=1) + "\n")
        print(json.dumps(snap, indent=1))
        return 0 if snap["integrity_check"] == "ok" else 1
    res = verify(a.db, json.loads(Path(a.snapshot).read_text()))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))
    return 1 if res["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
