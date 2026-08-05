"""Build the subset profile CSV for a targeted `discover` re-search.

Task 16: the full run's `discover` skipped 10,101 of 53,618 positioned profiles
because some already-stored granule happened to cover them in space and time, so
they never got their own CMR search. This reads those ids out of the run log and
writes the matching rows of the full selection to a new CSV, which
`pab --stage discover --profiles-csv <that> --replace` then re-searches.

    python rediscover_csv.py <run.log> <full_profiles.csv> <out.csv>
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


def skipped_ids(log_path: Path) -> list[str]:
    """``wmo_cycle`` ids from the **discover** summary's ``'skipped': [...]`` array.

    Scoped to lines carrying ``discover: {`` on purpose: ``ingest`` prints a
    ``'skipped'`` array too (the already-summarized profiles), and a bare search
    for ``'skipped'`` pulled in its 986 entries as well.

    Parsed with a regex rather than ``eval`` — the line is megabytes of
    machine-written text and there is no reason to execute it.
    """
    ids: list[str] = []
    with log_path.open(errors="replace") as fh:
        for line in fh:
            if "discover: {" not in line:
                continue
            m = re.search(r"'skipped': \[(.*?)\]", line, re.S)
            if m:
                ids.extend(re.findall(r"'(\d+_\d+)'", m.group(1)))
    return ids


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    log, full_csv, out_csv = (Path(a) for a in argv)

    ids = skipped_ids(log)
    wanted = {tuple(i.split("_")) for i in ids}
    print(f"skipped ids in log: {len(ids)} ({len(wanted)} unique)")

    with full_csv.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    keep = [r for r in rows if (r["wmo"], str(r["cycle"])) in wanted]
    print(f"full selection: {len(rows)} rows -> matched {len(keep)}")

    missing = len(wanted) - len(keep)
    if missing:
        print(f"WARNING: {missing} skipped ids not found in the full CSV")

    with out_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(keep)
    print(f"wrote {out_csv} with {len(keep)} profiles")
    return 0 if keep else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
