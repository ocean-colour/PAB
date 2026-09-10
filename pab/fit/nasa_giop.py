"""NASA PACE L2 IOP (GIOP) ingest — the NASA-baseline comparison against BING.

Design *Comparison & metrics*, "BING vs. NASA L2 IOP" (``PAB_design.md``);
full plan/decision record in ``claude_prompts/pace_giop_gsm.md``.

Writes a **parallel** ``fits`` row per matchup (``algorithm = 'NASA_GIOP'``,
sibling to the ``BING`` fit on the same ``matchup_id``/``pixel_id``, with its
own ``fit_id`` and ``pab_version``) rather than attaching to the existing BING
fit — the two "fits" have independent provenance, and NASA's values are not a
BING/MCMC fit at all (no chains, no LM warm-start; see Q6 of the prompt doc).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from pab.config import package_versions
from pab.pace import iop as _iop

_log = logging.getLogger("pab.fit.nasa_giop")

#: The ``fits.algorithm`` value for a NASA-GIOP ingest (not a BING fit).
ALGORITHM = "NASA_GIOP"


def make_nasa_giop_fit_id(matchup_id: str, ix: int, iy: int) -> str:
    """Deterministic fit id: ``"{matchup_id}_{ix}_{iy}_NASA_GIOP"``.

    Mirrors :func:`pab.fit.run.make_fit_id`'s
    ``{matchup_id}_{ix}_{iy}_{model_pair}`` scheme with the model tag swapped
    for the algorithm name.
    """
    return f"{matchup_id}_{int(ix)}_{int(iy)}_{ALGORITHM}"


def persist_nasa_giop(
    store,
    *,
    matchup_id: str,
    pixel_id: int | None,
    ix: int,
    iy: int,
    quantities: list[dict],
    pab_version: str,
    created: str | None = None,
) -> str:
    """Upsert the parallel ``fits`` row + namespaced ``NASA_GIOP_*`` results.

    Args:
        store: An open :class:`pab.db.store.Store`.
        matchup_id: The matchup this ingest belongs to.
        pixel_id: The (BING) matchup pixel this NASA-GIOP fit is a sibling of.
        ix, iy: The IOP granule's own pixel indices (see
            :func:`pab.pace.iop.nearest_pixel` — not necessarily identical to
            the AOP granule's ``ix``/``iy`` used by BING).
        quantities: Bare-name quantity dicts (see
            :func:`pab.pace.iop.extract_iop_quantities`).
        pab_version: Version to stamp on the new ``fits`` row.
        created: Timestamp override (else "now").

    Returns:
        The new NASA-GIOP ``fit_id``.
    """
    fit_id = make_nasa_giop_fit_id(matchup_id, ix, iy)
    created = created or datetime.now(UTC).isoformat()
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "pixel_id": pixel_id,
            "algorithm": ALGORITHM,
            "model_pair": None,
            "anw_model": None,
            "bbnw_model": None,
            "rrs_source": None,
            "prior_set": None,
            "nsteps": None,
            "nburn": None,
            "nwalkers": None,
            "wave_min": None,
            "wave_max": None,
            "chisq": None,
            "aic": None,
            "bic": None,
            "accept_frac": None,
            "success": 1,
            "chains_path": None,
            "figure_path": None,
            "pkg_versions": json.dumps(package_versions()),
            "pab_version": pab_version,
            "created": created,
        },
    )
    prefix = f"{ALGORITHM}_"
    rows = [
        {
            "fit_id": fit_id,
            "quantity": f"{prefix}{q['quantity']}",
            "value": q["value"],
            "value_lo": q["value_lo"],
            "value_hi": q["value_hi"],
            "unit": q["unit"],
        }
        for q in quantities
    ]
    # replace prior rows for this fit so a re-run leaves no stale quantities
    store.execute("DELETE FROM fit_results WHERE fit_id = ?", (fit_id,))
    store.upsert_many("fit_results", rows)
    return fit_id


def ingest_nasa_giop_matchup(
    store,
    matchup_id: str,
    *,
    cache_dir,
    rank: int = 1,
    pab_version: str,
    created: str | None = None,
) -> str:
    """Fetch + extract + persist NASA GIOP IOPs for one matchup's pixel.

    Locates the matchup's AOP granule, derives its co-temporal IOP granule
    (:func:`pab.pace.iop.iop_source_for_aop`), downloads it to ``cache_dir``
    (idempotent — reused on a re-run, the same robust streaming download the
    off-cloud ``--download`` path already uses), opens it locally, and finds
    the nearest pixel to the matchup pixel's *recorded* lat/lon (not by
    index — see :func:`pab.pace.iop.nearest_pixel`).

    Args:
        store: An open :class:`pab.db.store.Store`.
        matchup_id: The matchup to ingest.
        cache_dir: Local directory for the downloaded IOP granule.
        rank: Which matchup pixel to target (1 = nearest, matching the
            default BING fit pixel).
        pab_version: Version to stamp on the new ``fits`` row.
        created: Timestamp override.

    Returns:
        The new NASA-GIOP ``fit_id``.

    Raises:
        ValueError: if the matchup, its rank-``rank`` pixel, or its granule
            reference is missing.
    """
    from pab.pace.cloud import download_granule

    px = store.query(
        "SELECT * FROM matchup_pixels WHERE matchup_id = ? AND rank = ?",
        (matchup_id, rank),
    )
    if not px:
        raise ValueError(f"matchup {matchup_id!r} has no pixel with rank {rank}")
    px = px[0]
    m = store.query(
        "SELECT granule_id FROM matchups WHERE matchup_id = ?", (matchup_id,)
    )
    if not m:
        raise ValueError(f"no matchup {matchup_id!r}")
    gran = store.query(
        "SELECT data_url FROM granules WHERE granule_id = ?", (m[0]["granule_id"],)
    )
    aop_source = (
        gran[0]["data_url"] if gran and gran[0]["data_url"] else m[0]["granule_id"]
    )
    iop_source = _iop.iop_source_for_aop(aop_source)

    local = download_granule(iop_source, cache_dir)
    ds = _iop.open_iop_local(str(local))
    ix, iy, dist_km = _iop.nearest_pixel(ds, px["latitude"], px["longitude"])
    _log.info(
        "matchup %s: NASA-GIOP pixel %.4f km from the BING pixel", matchup_id, dist_km
    )
    quantities = _iop.extract_iop_quantities(ds, ix, iy)
    return persist_nasa_giop(
        store,
        matchup_id=matchup_id,
        pixel_id=px["pixel_id"],
        ix=ix,
        iy=iy,
        quantities=quantities,
        pab_version=pab_version,
        created=created,
    )


def build_nasa_giop(
    store,
    *,
    cache_dir,
    replace: bool = False,
    pab_version: str,
    created: str | None = None,
    matchup_ids: list[str] | None = None,
) -> dict[str, list[str]]:
    """NASA-GIOP ingest for matchups with a completed BING fit (idempotent).

    Mirrors :func:`pab.fit.run.build_fits`'s skip/replace/failed-batch shape.
    Restricted to matchups that already have a ``BING`` fit (the design's
    "same pixel already used for the BING fit" requirement); a matchup
    already ingested (by fit_id) is skipped unless ``replace``.

    Args:
        store: An open :class:`pab.db.store.Store`.
        cache_dir: Local directory for downloaded IOP granules.
        replace: Re-ingest matchups that already have a NASA-GIOP fit.
        pab_version: Version to stamp on new ``fits`` rows.
        created: Timestamp override.
        matchup_ids: Optional explicit subset (the dev-set prototype path);
            omit to sweep every matchup with a BING fit.

    Returns:
        ``{"written": [...], "skipped": [...], "failed": [...]}`` — all lists
        hold matchup ids, except ``written`` holds the new fit ids (one per
        matchup; the ingested pixel indices aren't known until the IOP
        granule's own nearest-pixel search runs, so the skip-check keys on
        ``matchup_id`` rather than a precomputed ``fit_id``).
    """
    written: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    done: set[str] = set()
    if not replace:
        done = {
            r["matchup_id"]
            for r in store.query(
                f"SELECT matchup_id FROM fits WHERE algorithm = '{ALGORITHM}'"
            )
        }

    sql = (
        "SELECT DISTINCT m.matchup_id FROM matchups m "
        "JOIN fits f ON f.matchup_id = m.matchup_id AND f.algorithm = 'BING' "
    )
    params: tuple = ()
    if matchup_ids is not None:
        placeholders = ", ".join("?" for _ in matchup_ids)
        sql += f"WHERE m.matchup_id IN ({placeholders}) "
        params = tuple(matchup_ids)
    sql += "ORDER BY m.matchup_id"

    for row in store.query(sql, params):
        matchup_id = row["matchup_id"]
        if matchup_id in done:
            skipped.append(matchup_id)
            continue
        try:
            fit_id = ingest_nasa_giop_matchup(
                store,
                matchup_id,
                cache_dir=cache_dir,
                pab_version=pab_version,
                created=created,
            )
            written.append(fit_id)
        except Exception:  # noqa: BLE001 -- one bad matchup must not abort the batch
            _log.exception("NASA-GIOP ingest failed for %s", matchup_id)
            failed.append(matchup_id)
    return {"written": written, "skipped": skipped, "failed": failed}


def main(argv=None) -> int:
    """CLI driver: ``python -m pab.fit.nasa_giop --db DB --cache-dir DIR``.

    Thin, resumable wrapper around :func:`build_nasa_giop` (idempotent — a
    re-run skips matchups already ingested). ``--db`` is required and never
    created (``Store.open(create=False)``): the production DB path must be
    given explicitly, per the one-canonical-DB working agreement.
    """
    import argparse
    import time

    from pab import config
    from pab.db import Store

    p = argparse.ArgumentParser(
        prog="python -m pab.fit.nasa_giop",
        description="NASA-GIOP L2 IOP ingest for matchups with a BING fit.",
    )
    p.add_argument("--db", required=True, help="Existing PAB SQLite store.")
    p.add_argument(
        "--cache-dir", required=True, help="Local cache for downloaded IOP granules."
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ingest at most N matchups (in matchup_id order; skipped/already-"
        "ingested matchups count toward N, so a re-run covers the same slice).",
    )
    p.add_argument(
        "--matchup",
        action="append",
        default=None,
        help="Explicit matchup_id to ingest (repeatable; overrides --limit).",
    )
    p.add_argument("--replace", action="store_true", help="Re-ingest existing fits.")
    p.add_argument("--log-file", default=None, help="Also log to this file.")
    args = p.parse_args(argv)

    handlers = [logging.StreamHandler()]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )

    with Store.open(args.db, create=False) as store:
        matchup_ids = args.matchup
        if matchup_ids is None and args.limit is not None:
            matchup_ids = [
                r["matchup_id"]
                for r in store.query(
                    "SELECT DISTINCT m.matchup_id FROM matchups m "
                    "JOIN fits f ON f.matchup_id = m.matchup_id "
                    "AND f.algorithm = 'BING' "
                    "ORDER BY m.matchup_id LIMIT ?",
                    (args.limit,),
                )
            ]
        t0 = time.monotonic()
        result = build_nasa_giop(
            store,
            cache_dir=args.cache_dir,
            replace=args.replace,
            pab_version=config.pab_version,
            matchup_ids=matchup_ids,
        )
        elapsed = time.monotonic() - t0

    n_run = len(result["written"]) + len(result["failed"])
    rate = elapsed / n_run if n_run else float("nan")
    _log.info(
        "nasa-giop done: written %d, skipped %d, failed %d in %.1f s (%.2f s/matchup)",
        len(result["written"]),
        len(result["skipped"]),
        len(result["failed"]),
        elapsed,
        rate,
    )
    if result["failed"]:
        _log.warning("failed matchups: %s", result["failed"])
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
