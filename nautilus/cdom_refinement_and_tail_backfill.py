"""Combined driver: CDOM QC/sensor refinement + the un-matched-tail backfill.

Ties together two independently-motivated passes that JXP asked to run
together (chl_cdom_matchups.md Report/Tasks item 5), since both need a
Nautilus re-ingestion/re-run cycle and republish, and doing them once avoids
paying that overhead twice:

1. **CDOM refinement** (chl_cdom_matchups.md R2 + R6): a QC-filtered CDOM
   mixed-layer mean (dropping Argo QC=4 "bad" points before averaging) and a
   per-float CDOM sensor-model lookup (``MCOMS_FLBBCD`` vs. ``ECO_FLBBCD``).
   Both were deferred from the R1-R8 figure-refinement pass pending this
   combined re-ingestion. The QC-filtered fields need a full profile-level
   re-fetch (``pab --stage ingest --replace``) — they are now computed
   automatically by ``pab.argo.summary.summarize_profile``/``persist_summary``
   as part of *any* such re-ingest, so no separate driver logic is needed for
   that half; this script only handles the float-level sensor-model lookup
   (``sensor-models`` subcommand below) and re-deriving the sensor-model
   CSV/report.

2. **The un-matched-tail backfill** (``claude_prompts/hyper_matchups.md`` /
   ``backfill_unmatched.md`` on the ``hyper_matchups`` branch): the full-run
   ``match`` stage stopped at ``profile_id = 52341``, leaving ~1,690 profiles
   never attempted. ``pab.matchup.engine.build_matchups``/
   ``pab.pipeline.match`` now accept a ``selection`` (this session's schema/
   engine change, mirroring ``discover``'s existing ``PipelineConfig.
   selection_keys()`` pattern), so completing the tail no longer requires
   re-sweeping the whole store. This script's ``tail-csv`` subcommand
   re-derives the tail **fresh** each time it's run — it is deliberately not
   a hardcoded "profile_id > 52341" constant, so it re-verifies
   backfill_unmatched.md's Task 1 claim against whatever the DB actually
   holds at run time, rather than trusting a number found once weeks ago.

Neither subcommand here touches ``matchups``/``fits``/``mld_summary`` values
in the way the real re-ingestion + match/fit/figure completion does — this
script only prepares inputs (the tail CSV) and does the one truly
independent, cheap, additive piece (sensor models). **The actual multi-hour
re-ingestion and match/fit/figure completion are not run by this script** —
see the module docstring's "Full sequence" section below for the exact `pab`
CLI invocations, which need Nautilus (or at minimum a machine with
in-region/`--download` granule access) and were not run from here.

Usage
-----
    # Re-derive the un-matched tail and write it as a --profiles-csv input.
    # Also re-verifies backfill_unmatched.md's Task 1 claim against the
    # current DB (prints the same reconciliation table that doc's Task 1 asks
    # for) rather than assuming the old 52341/1690/1524 numbers still hold.
    python nautilus/cdom_refinement_and_tail_backfill.py tail-csv \\
        --db /path/to/pab.db --out tail_profiles.csv

    # Backfill floats.cdom_sensor_model for every float with data_center set
    # (cheap: one small HTTPS GET per float, no profile re-fetch). Safe to run
    # standalone, independent of the tail backfill.
    python nautilus/cdom_refinement_and_tail_backfill.py sensor-models \\
        --db /path/to/pab.db

Full sequence (for the record — not automated here; needs Nautilus):

    # 0. Push the authoritative local pab.db (schema already migrated to v5
    #    by opening it once with pab.db.Store.open, or by running any pab
    #    CLI command against it) to wherever the run happens. Never merge two
    #    SQLite files (backfill_unmatched.md's working agreement).

    # 1. Re-verify the tail claim fresh (this script):
    python nautilus/cdom_refinement_and_tail_backfill.py tail-csv \\
        --db pab.db --out tail_profiles.csv

    # 2. CDOM QC-filtered re-ingestion: a full replace=True re-fetch, exactly
    #    like chl_cdom_prompt_1.md's Stage 10 re-ingestion, over the existing
    #    881 floats. cdom_qc_filtered/cdom_qc_filtered_std/cdom_n_qc4_dropped
    #    are populated automatically as part of this — no new flag needed.
    pab --db pab.db --stage ingest --replace --jobs 16

    # 3. CDOM sensor-model backfill (this script, cheap, float-level):
    python nautilus/cdom_refinement_and_tail_backfill.py sensor-models \\
        --db pab.db

    # 4. Backfill discover for the tail (some of it may never have been
    #    searched — backfill_unmatched.md Task 4):
    pab --db pab.db --stage discover --profiles-csv tail_profiles.csv \\
        --discover-jobs 8

    # 5. Complete match for the tail ONLY (the new selection targeting):
    pab --db pab.db --stage match --profiles-csv tail_profiles.csv --jobs 16
    #    Check the printed/logged reconciliation: written + skipped +
    #    unmatched == qualifying_total. A mismatch means something silently
    #    dropped profiles (backfill_unmatched.md Task 7's guard) — stop and
    #    investigate rather than continuing to fit/figure.

    # 6. fit + figure need no special targeting — both are already idempotent
    #    by fit_id/matchup_id, so a plain re-run only does work for the
    #    matchups step 5 just created:
    pab --db pab.db --stage fit --jobs 16
    pab --db pab.db --stage figure --jobs 16

    # 7. Re-publish once (covers both the CDOM refinement and the tail
    #    backfill in a single push): verify integrity + row counts, upload to
    #    s3://pab/full/pab.db, round-trip-verify by sha256 (not just a clean
    #    CLI exit — see chl_cdom_prompt_1.md Task 6's precedent), rclone to
    #    AIOcean:PAB/. Resolve pab_version (stay at 1.0 as a documented
    #    backfill exception, matching both prior precedents, or bump — that
    #    call belongs to JXP, per backfill_unmatched.md Q3).

    # 8. Correct the docs (PAB_full_run_report.md's match-rate denominator,
    #    PAB_implementation.md, HOWTO.md) and update chl_cdom_matchups.md /
    #    hyper_matchups.md's Logs with the final counts (the hyperspectral
    #    float 7902260 should go from 0 to ~25-30 matchups).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def derive_tail(store) -> tuple[list[dict], int, int]:
    """Re-derive the un-matched tail fresh from the live DB.

    Returns:
        ``(tail_profiles, last_matched_profile_id, qualifying_with_candidates)``
        — the profiles with ``profile_id`` beyond the highest one currently
        carrying a matchup, and how many of *those* have at least one
        candidate granule (the ceiling on how many could possibly match,
        mirroring ``nautilus/coverage_check.py``'s method exactly rather than
        reinventing the candidate test).
    """
    from pab.matchup.engine import GranuleIndex, MatchupConfig, qualifying_profiles

    last_matched = store.query("SELECT MAX(profile_id) AS m FROM matchups")[0]["m"]
    if last_matched is None:
        raise RuntimeError("no matchups in this DB yet — nothing to call a 'tail'")

    qualifying = qualifying_profiles(store)
    tail = [p for p in qualifying if p["profile_id"] > last_matched]

    cfg = MatchupConfig()
    index = GranuleIndex.load(store)
    with_candidates = 0
    for p in tail:
        if p["latitude"] is None or p["longitude"] is None:
            continue
        cands = index.candidates(
            p["time"],
            dtime_max_hours=cfg.dtime_max_hours,
            latitude=p["latitude"],
            longitude=p["longitude"],
            pad_deg=cfg.footprint_pad_deg,
        )
        if cands:
            with_candidates += 1

    return tail, last_matched, with_candidates


def cmd_tail_csv(args: argparse.Namespace) -> int:
    from pab.db import Store

    with Store.open(Path(args.db), create=False) as store:
        tail, last_matched, with_candidates = derive_tail(store)
        total_qualifying = len(
            store.query(
                "SELECT p.profile_id FROM profiles p "
                "JOIN mld_summary m ON p.profile_id = m.profile_id"
            )
        )

    print(f"last profile_id carrying a matchup: {last_matched}")
    print(f"qualifying profiles overall: {total_qualifying}")
    print(f"tail (profile_id > {last_matched}): {len(tail)}")
    print(f"  ...of those, with >=1 candidate granule: {with_candidates}")
    print(
        "  (compare against backfill_unmatched.md's recorded 52341 / 1690 / "
        "1524 — a large discrepancy here means the DB has changed since that "
        "doc's investigation and its Task 1 conclusion should be re-checked, "
        "not assumed)"
    )

    if not tail:
        print("no tail to write — nothing beyond the last matched profile_id")
        return 0

    with Path(args.out).open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["wmo", "cycle", "latitude", "longitude", "time"]
        )
        w.writeheader()
        for p in tail:
            w.writerow({k: p[k] for k in w.fieldnames})
    print(f"wrote {len(tail)} rows -> {args.out}")
    return 0


def cmd_sensor_models(args: argparse.Namespace) -> int:
    from pab.argo.fetch import fetch_cdom_sensor_model
    from pab.argo.summary import persist_cdom_sensor_model
    from pab.db import Store

    with Store.open(Path(args.db), create=False) as store:
        floats = store.query(
            "SELECT wmo, data_center FROM floats WHERE data_center IS NOT NULL"
        )
        print(f"{len(floats)} floats have a known data_center")
        found, missing = 0, 0
        for i, row in enumerate(floats, 1):
            model = fetch_cdom_sensor_model(row["wmo"], row["data_center"])
            persist_cdom_sensor_model(store, wmo=row["wmo"], sensor_model=model)
            if model is None:
                missing += 1
            else:
                found += 1
            if i % 100 == 0:
                print(
                    f"  {i}/{len(floats)} processed "
                    f"({found} found, {missing} missing/unmapped)"
                )
    print(
        f"done: {found} sensor models found, {missing} missing/unmapped, "
        f"out of {len(floats)} floats"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="command", required=True)

    tail = sub.add_parser("tail-csv", help="re-derive the un-matched tail as a CSV")
    tail.add_argument("--db", required=True)
    tail.add_argument("--out", default="tail_profiles.csv")
    tail.set_defaults(func=cmd_tail_csv)

    sensors = sub.add_parser("sensor-models", help="backfill floats.cdom_sensor_model")
    sensors.add_argument("--db", required=True)
    sensors.set_defaults(func=cmd_sensor_models)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
