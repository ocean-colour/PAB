"""Report how many profiles have candidate granules — the ceiling on `match`.

Task 16's verification. A plain `discover` cannot answer this: it skips profiles
that *have* coverage, so its skip count says nothing about whether a profile was
ever searched. This instead asks the question match will ask — for every
positioned profile, how many granules pass the time window + footprint test — and
does it entirely from the store, with no CMR queries.

    python coverage_check.py <pab.db>
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2

    from pab.db import Store
    from pab.matchup.engine import GranuleIndex, MatchupConfig

    cfg = MatchupConfig()
    with Store.open(Path(argv[0]), create=False) as store:
        index = GranuleIndex.load(store)
        profiles = store.query(
            "SELECT p.profile_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time "
            "FROM profiles p JOIN mld_summary m ON p.profile_id = m.profile_id "
            "WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL"
        )
        n_matchups = store.count("matchups")
    print(f"granules indexed: {len(index):,}")
    print(f"positioned profiles with a summary: {len(profiles):,}")

    hist = Counter()
    for p in profiles:
        # the pad match itself uses, so this is the candidate count match will see
        n = len(
            index.candidates(
                p["time"],
                dtime_max_hours=cfg.dtime_max_hours,
                latitude=p["latitude"],
                longitude=p["longitude"],
                pad_deg=cfg.footprint_pad_deg,
            )
        )
        hist[min(n, 10)] += 1

    with_any = sum(c for n, c in hist.items() if n > 0)
    total = len(profiles)
    print(f"\nprofiles with >=1 candidate: {with_any:,} / {total:,} "
          f"({100 * with_any / total:.1f}%)")
    print(f"profiles with 0 candidates: {total - with_any:,} "
          f"(can never match, whatever match does)")
    print("\ncandidate-count distribution (10 = 10 or more):")
    for n in sorted(hist):
        print(f"  {n:>2}: {hist[n]:>7,}")
    mean = sum(n * c for n, c in hist.items()) / total
    print(f"\nmean candidates/profile (capped at 10): {mean:.2f}")
    print(f"matchups already in the store: {n_matchups:,}")
    print(
        f"=> match has up to {with_any:,} profiles to work with; at the pilot's "
        f"28% rate that projects to ~{int(0.28 * with_any):,} matchups"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
