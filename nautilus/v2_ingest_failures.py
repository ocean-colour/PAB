"""Write the list of profiles that failed ingest, for JXP to chase (Q1b).

Run after the resume pass. A profile is a *failure* if it is in the selection
CSV but did not end up as a usable record, and the two ways that happens need
telling apart because they are different conversations to have with a DAC:

* ``no_profile_row`` — argopy returned nothing at all for ``(wmo, cycle)``.
  Either the profile is not in the GDAC, or every fetch attempt errored. The
  exception class is recovered from the run log where available.
* ``no_mld_summary`` — argopy *did* return the profile, but it carried no
  usable ``BBP700``/``CHLA``, so no mixed-layer summary could be computed.
  These exist; they just are not BGC-usable.

Usage: v2_ingest_failures.py <db> <selection.csv> <out.csv> [run.log]
"""

import csv
import re
import sqlite3
import sys
from pathlib import Path

db_path, sel_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
log_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None

con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
profiles = {
    (int(w), int(c)): pid
    for w, c, pid in con.execute("SELECT wmo, cycle, profile_id FROM profiles")
}
with_mld = {r[0] for r in con.execute("SELECT profile_id FROM mld_summary")}
con.close()

# Last logged exception per "<wmo>_<cycle>", if a run log is available.
reasons = {}
if log_path and log_path.is_file():
    key = None
    for line in log_path.read_text(errors="replace").splitlines():
        m = re.search(r"(?:ingest|profile) failed for (\d+)_(\d+)", line)
        if m:
            key = f"{m.group(1)}_{m.group(2)}"
            continue
        if key and re.match(r"^[A-Za-z_.]+(Error|Exception|Timeout)\b", line.strip()):
            reasons[key] = line.strip()[:200]
            key = None

with open(sel_path) as fh:
    rows = list(csv.DictReader(fh))

out, n_ok = [], 0
for r in rows:
    k = (int(r["wmo"]), int(r["cycle"]))
    pid = profiles.get(k)
    if pid is None:
        why = "no_profile_row: argopy returned nothing for this (wmo, cycle)"
        extra = reasons.get(f"{k[0]}_{k[1]}")
        if extra:
            why += f" [{extra}]"
    elif pid not in with_mld:
        why = "no_mld_summary: profile fetched, but no usable BBP700/CHLA"
    else:
        n_ok += 1
        continue
    out.append({**{c: r.get(c, "") for c in
                   ("wmo", "cycle", "date", "latitude", "longitude")},
                "has_position": bool(str(r.get("latitude", "")).strip()
                                     and str(r.get("latitude")) != "nan"),
                "reason": why})

with open(out_path, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["wmo", "cycle", "date", "latitude",
                                       "longitude", "has_position", "reason"])
    w.writeheader()
    w.writerows(out)

kinds = {}
for r in out:
    kinds[r["reason"].split(":")[0]] = kinds.get(r["reason"].split(":")[0], 0) + 1
noposs = sum(1 for r in out if not r["has_position"])
print(f"selection {len(rows)} | ingested OK {n_ok} | FAILED {len(out)} "
      f"({100 * len(out) / max(len(rows), 1):.1f}%)")
for k, v in sorted(kinds.items()):
    print(f"   {k}: {v}")
print(f"   of the failures, {noposs} had no position in the selection CSV")
print(f"wrote {out_path}")
