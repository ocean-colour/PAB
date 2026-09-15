"""The ``geometry`` stage: per-pixel viewing geometry from PACE L1B.

Fills ``matchup_pixels.theta_s`` / ``theta_v`` / ``dphi`` / ``geom_source``
(schema v5) from the co-temporal L1B granule, so the inelastic RT backend has
the angles it needs **before** the ``fit`` stage runs.

It is a separate stage, between ``match`` and ``fit``, for one reason: the work
is **per granule, not per fit**. Today's store holds 146,100 pixels across
11,494 distinct granules, so grouping by granule turns 146,100 potential opens
into 11,494 — and doing it inside ``fit`` would pay that 1.8 GB open in the
serial parent loop instead of fanning it out.

Shape follows ``match`` (:mod:`pab.matchup.engine`): the parent reads the work
list and performs **every** DB write; workers only open granules and read
values, so there is a single SQLite writer and no lock contention. Idempotent —
pixels that already have ``theta_s`` are skipped before any granule is opened,
so a resumed run does zero network work for them.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from pab.pace import l1b
from pab.parallel import PROGRESS_EVERY, init_worker, picklable

_log = logging.getLogger(__name__)

#: Max separation (degrees, per axis) between the stored pixel's lat/lon and the
#: L1B pixel's before :class:`pab.pace.l1b.GridMismatchError` is raised.
DEFAULT_TOL_DEG = 0.01

#: Per-granule open+read bound, seconds (see :data:`pab.pace.l1b.OPEN_TIMEOUT_S`).
DEFAULT_TIMEOUT_S = l1b.OPEN_TIMEOUT_S


def pixels_needing_geometry(store, *, replace: bool = False) -> list[dict[str, Any]]:
    """Rows to fill, ordered by granule then pixel.

    Each row carries the pixel's identity and position plus the granule
    ``source`` (``granules.data_url`` if present, else the ``granule_id`` —
    the same convention :class:`pab.matchup.engine.GranuleIndex` uses).

    Args:
        store: An open :class:`pab.db.store.Store`.
        replace: Include pixels that already have geometry.

    Returns:
        A list of dicts with ``pixel_id``, ``matchup_id``, ``ix``, ``iy``,
        ``latitude``, ``longitude``, ``granule_id``, ``source``.
    """
    where = "" if replace else "WHERE p.theta_s IS NULL"
    return store.query(
        "SELECT p.pixel_id, p.matchup_id, p.ix, p.iy, p.latitude, p.longitude, "
        "       m.granule_id, COALESCE(g.data_url, m.granule_id) AS source "
        "FROM matchup_pixels p "
        "JOIN matchups m ON m.matchup_id = p.matchup_id "
        "LEFT JOIN granules g ON g.granule_id = m.granule_id "
        f"{where} "
        "ORDER BY m.granule_id, p.pixel_id"
    )


def group_by_granule(rows) -> dict[str, list[dict[str, Any]]]:
    """Group :func:`pixels_needing_geometry` rows by granule ``source``."""
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r["source"]].append(dict(r))
    return dict(out)


def open_geolocation(source, *, opener=None, timeout_s: float = DEFAULT_TIMEOUT_S):
    """Open the L1B geolocation for an **AOP** granule source.

    Resolves the AOP granule to its L1B URL via CMR
    (:func:`pab.pace.l1b.l1b_source_for_aop`) and opens that, bounded by
    ``timeout_s``. ``opener`` short-circuits both — it maps the AOP source
    straight to a geolocation dataset, which is the offline test seam.
    """
    if opener is not None:
        return opener(source)
    return l1b.open_l1b_geolocation(l1b.l1b_source_for_aop(source), timeout_s=timeout_s)


def geometry_for_granule(
    source,
    pixels,
    *,
    opener=None,
    tol_deg: float = DEFAULT_TOL_DEG,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> tuple[list[tuple], list[tuple]]:
    """Read the geometry for one granule's pixels. **Runs in a worker.**

    Module-level and picklable so it can be submitted to a process pool.

    A pixel that fails its grid check is **recorded, not raised** — one bad
    pixel must not cost the granule's other nine. A failure to open the granule
    at all does propagate, and the caller records the whole granule as failed.

    Args:
        source: The AOP granule source (URL or id).
        pixels: That granule's rows from :func:`pixels_needing_geometry`.
        opener: Test seam — AOP ``source`` → geolocation dataset.
        tol_deg: Grid-check tolerance.
        timeout_s: Per-granule open bound.

    Returns:
        ``(filled, mismatched)`` — ``filled`` is
        ``[(pixel_id, theta_s, theta_v, dphi), ...]`` and ``mismatched`` is
        ``[(pixel_id, reason), ...]``.
    """
    filled: list[tuple] = []
    mismatched: list[tuple] = []
    ds = open_geolocation(source, opener=opener, timeout_s=timeout_s)
    try:
        for px in pixels:
            try:
                theta_s, theta_v, dphi = l1b.pixel_geometry(
                    ds,
                    px["ix"],
                    px["iy"],
                    lat=px["latitude"],
                    lon=px["longitude"],
                    tol_deg=tol_deg,
                )
            except (l1b.GridMismatchError, ValueError, IndexError) as exc:
                mismatched.append((px["pixel_id"], f"{type(exc).__name__}: {exc}"))
                continue
            filled.append((px["pixel_id"], theta_s, theta_v, dphi))
    finally:
        try:
            ds.close()
        except Exception:  # noqa: BLE001 — a close failure must not lose the reads
            pass
    return filled, mismatched


def build_geometry(
    store,
    *,
    opener=None,
    replace: bool = False,
    jobs: int = 1,
    tol_deg: float = DEFAULT_TOL_DEG,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    geom_source: str = l1b.GEOM_SOURCE,
) -> dict[str, list]:
    """Fill every matchup pixel's viewing geometry; return a run summary.

    Idempotent and resumable: pixels with ``theta_s`` already set are skipped
    **before** their granule is opened, so a resumed run does no network work
    for them. ``replace=True`` refills everything.

    ``jobs > 1`` reads granules in parallel worker processes while the parent
    stays the only DB writer. Workers are spawned, so an injected ``opener``
    must be picklable (a module-level function); a closure or lambda silently
    falls back to the serial path — the same contract as ``match``.

    Args:
        store: An open :class:`pab.db.store.Store` at schema v5 or later.
        opener: Test seam — AOP granule ``source`` → geolocation dataset.
        replace: Refill pixels that already have geometry.
        jobs: Granule-level worker processes (1 = serial).
        tol_deg: Grid-check tolerance in degrees.
        timeout_s: Per-granule open bound in seconds.
        geom_source: Value stamped into ``matchup_pixels.geom_source``.

    Returns:
        ``{"written": [pixel_id...], "skipped": [pixel_id...],
        "failed": [granule_id...], "mismatched": [(pixel_id, reason)...]}``.
        ``failed`` holds granules that could not be read at all; ``mismatched``
        holds individual pixels that failed the grid check. Neither aborts the
        stage.
    """
    todo_rows = pixels_needing_geometry(store, replace=replace)
    by_granule = group_by_granule(todo_rows)

    skipped: list[int] = []
    if not replace:
        skipped = [
            r["pixel_id"]
            for r in store.query(
                "SELECT pixel_id FROM matchup_pixels WHERE theta_s IS NOT NULL"
            )
        ]

    written: list[int] = []
    failed: list[str] = []
    mismatched: list[tuple] = []

    if not by_granule:
        _log.info("geometry: nothing to do (%d pixels already filled)", len(skipped))
        return {
            "written": written,
            "skipped": skipped,
            "failed": failed,
            "mismatched": mismatched,
        }

    # granule source -> granule_id, for the failed list (ids, not URLs)
    gid = {rows[0]["source"]: rows[0]["granule_id"] for rows in by_granule.values()}

    def record(source, result) -> None:
        filled, bad = result
        for pixel_id, theta_s, theta_v, dphi in filled:
            store.execute(
                "UPDATE matchup_pixels SET theta_s = ?, theta_v = ?, dphi = ?, "
                "geom_source = ? WHERE pixel_id = ?",
                (theta_s, theta_v, dphi, geom_source, pixel_id),
            )
            written.append(pixel_id)
        for pixel_id, reason in bad:
            _log.warning(
                "geometry grid check failed for pixel %s: %s", pixel_id, reason
            )
            mismatched.append((pixel_id, reason))

    _log.info(
        "geometry: %d pixels over %d granules (%d pixels already filled)",
        len(todo_rows),
        len(by_granule),
        len(skipped),
    )

    if jobs and int(jobs) > 1 and picklable(opener):
        _geometry_parallel(
            by_granule, int(jobs), opener, tol_deg, timeout_s, record, failed, gid
        )
    else:
        for i, (source, pixels) in enumerate(by_granule.items(), start=1):
            try:
                record(
                    source,
                    geometry_for_granule(
                        source,
                        pixels,
                        opener=opener,
                        tol_deg=tol_deg,
                        timeout_s=timeout_s,
                    ),
                )
            except Exception:  # noqa: BLE001 — one bad granule must not abort
                _log.exception("geometry failed for granule %s", source)
                failed.append(gid[source])
            if i % PROGRESS_EVERY == 0:
                _log.info(
                    "geometry progress: %d/%d granules (%d pixels written, "
                    "%d granules failed)",
                    i,
                    len(by_granule),
                    len(written),
                    len(failed),
                )

    _log.info(
        "geometry done: %d pixels written, %d skipped, %d granules failed, "
        "%d pixels mismatched",
        len(written),
        len(skipped),
        len(failed),
        len(mismatched),
    )
    return {
        "written": written,
        "skipped": skipped,
        "failed": failed,
        "mismatched": mismatched,
    }


def _geometry_parallel(
    by_granule, jobs, opener, tol_deg, timeout_s, record, failed, gid
) -> None:
    """Read granules across worker processes; ``record`` writes in the parent.

    Each worker bounds its own open with :data:`timeout_s` (the SIGALRM guard in
    :func:`pab.pace.l1b.open_l1b_geolocation` works in a worker, whose own main
    thread it runs on), so a wedged granule read cannot stall the pool the way
    it could in ``match``.
    """
    import multiprocessing as mp
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    fut_src: dict = {}
    pending: set = set()
    total = len(by_granule)
    done_count = 0
    _log.info("geometry: %d granules over %d processes", total, jobs)

    def _drain(fut) -> None:
        nonlocal done_count
        source = fut_src.pop(fut)
        try:
            record(source, fut.result())
        except Exception:  # noqa: BLE001 — one bad granule must not abort the batch
            _log.exception("geometry failed for granule %s", source)
            failed.append(gid[source])
        done_count += 1
        if done_count % PROGRESS_EVERY == 0:
            _log.info("geometry progress: %d/%d granules", done_count, total)

    with ProcessPoolExecutor(
        max_workers=jobs, mp_context=mp.get_context("spawn"), initializer=init_worker
    ) as ex:
        for source, pixels in by_granule.items():
            fut = ex.submit(
                geometry_for_granule,
                source,
                pixels,
                opener=opener,
                tol_deg=tol_deg,
                timeout_s=timeout_s,
            )
            fut_src[fut] = source
            pending.add(fut)
            if len(pending) >= 2 * jobs:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in done:
                    _drain(f)
        for f in wait(pending).done:
            _drain(f)
