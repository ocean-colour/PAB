"""Space + time matchup engine (Stage 4).

Joins the two halves built in Stages 2–3 — BGC-Argo mixed-layer summaries
(:mod:`pab.argo`) and PACE granules (:mod:`pab.pace`) — into **matchup
records**. For each qualifying profile (one with a mixed-layer summary) the
engine finds the PACE granule whose acquisition time is within a configurable
window of the profile time *and* whose footprint covers the float, extracts the
~10 nearest **unflagged** ``Rrs`` spectra around the float, and writes the
record linking **float ↔ granule ↔ pixels** through :class:`pab.db.store.Store`.

Design notes (``docs/design/PAB_design.md`` → *Matchup, use, and analysis*; the
Bisson et al. recipe in ``docs/context.md`` §3):

* **Temporal match** — ``|profile_time − granule_time|`` within
  :attr:`MatchupConfig.dtime_max_hours` (default 24 h; tighten toward ~3 h as
  data allow). Recorded as ``dtime_hours``.
* **Spatial match** — the nearest unflagged pixel must lie within
  :attr:`MatchupConfig.max_distance_km` of the float (the footprint actually
  covers the float, not merely a temporal coincidence). The ~10 nearest
  unflagged pixels are selected via :mod:`pab.pace.extract`, approximating the
  small (5×5) unflagged box Bisson et al. use.
* **Selection rule** — when several granules qualify, pick the closest in space
  (nearest-pixel ``distance_km``), breaking ties by smallest ``dtime_hours``,
  then by more spectra, then by ``granule_id`` (deterministic).
* **Deterministic ``matchup_id``** — ``"{wmo}_{cycle}_{granule_id}"`` so re-runs
  upsert idempotently.

The geometry/time logic is kept in pure functions operating on values/arrays,
and granule datasets are obtained via the :func:`pab.pace.cloud.open_granule`
seam (``opener=`` injects synthetic granules in tests — no network/S3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from pab.config import pab_version
from pab.pace import cloud
from pab.pace import extract as _extract
from pab.pace import flags as _flags
from pab.parallel import PROGRESS_EVERY, init_worker, picklable

_log = logging.getLogger("pab.match")

__all__ = [
    "MatchupConfig",
    "Matchup",
    "make_matchup_id",
    "parse_time",
    "time_offset_hours",
    "footprint_bbox",
    "footprint_covers",
    "GranuleIndex",
    "find_matchup",
    "write_matchup",
    "qualifying_profiles",
    "candidate_granules",
    "build_matchups",
]


@dataclass(frozen=True)
class MatchupConfig:
    """Tunable criteria for the matchup engine.

    Attributes:
        dtime_max_hours: Maximum ``|profile − granule|`` time offset (hours) for
            a granule to qualify. Default 24 h (the design's loose bound;
            tighten toward ~3 h per Bisson et al. as data density allows).
        n_spectra: Number of nearest unflagged pixels/spectra to select
            (~10 ≈ the central part of a 5×5 box).
        max_distance_km: Maximum float→nearest-pixel distance (km) for a granule
            to count as spatially covering the float.
        mask_flags: ``l2_flags`` names that reject a pixel (the standard ocean
            screen by default).
        footprint_pad_deg: Slack (degrees) added to a granule's footprint
            bounding box in the cheap spatial pre-filter
            (:class:`GranuleIndex`). Generous by design — CMR footprints are
            4-corner approximations of a curved swath, so the box can cut the
            true edge by tens of km; the exact test is still the
            nearest-unflagged-pixel distance in :func:`find_matchup`.
        stall_timeout_s: In the parallel path, how long a chunk of profiles may
            go with **no** completed result at all before its workers are declared
            wedged and killed (see :func:`_build_matchups_parallel`). A healthy
            chunk completes something every few seconds, so 2 min is already very
            conservative — and the cost matters: each firing waits out the whole
            timeout, so 10 min would add ~36 h of pure waiting over the full
            selection at the observed wedge rate.
        open_timeout_s: Per-granule read timeout (:func:`_open_with_timeout`).
            The backstop above only fires when a whole chunk goes quiet; this
            catches the actual culprit — one granule read that never returns —
            and lets the profile try its other candidates.
    """

    dtime_max_hours: float = 24.0
    n_spectra: int = 10
    max_distance_km: float = 5.0
    mask_flags: tuple[str, ...] = field(default=_flags.STANDARD_OCEAN_MASK)
    footprint_pad_deg: float = 1.0
    stall_timeout_s: float = 120.0
    open_timeout_s: float = 120.0


@dataclass
class Matchup:
    """One profile↔granule matchup with its selected pixels.

    The scalar fields map onto the ``matchups`` row; ``pixels`` are the
    per-pixel records (each from :func:`pab.pace.extract.extract_matchup_spectra`,
    i.e. carrying ``ix``/``iy``/``latitude``/``longitude``/``distance_km``/
    ``rank``/``flagged`` plus the ``Rrs`` arrays) that become ``matchup_pixels``
    rows.
    """

    matchup_id: str
    granule_id: str
    distance_km: float
    dtime_hours: float
    n_spectra: int
    pixels: list[dict[str, Any]]
    profile_id: int | None = None


def make_matchup_id(wmo: int, cycle: int, granule_id: str) -> str:
    """Deterministic matchup id encoding the profile and granule.

    ``"{wmo}_{cycle}_{granule_id}"`` — stable across re-runs so writes upsert
    idempotently.
    """
    return f"{wmo}_{cycle}_{granule_id}"


def parse_time(value: Any) -> datetime:
    """Parse an ISO-8601 timestamp to a UTC-aware :class:`datetime`.

    Accepts a trailing ``Z`` and naive strings (assumed UTC); also accepts a
    ``datetime`` or ``numpy.datetime64`` directly.

    Raises:
        ValueError: if ``value`` is ``None`` or cannot be parsed.
    """
    if value is None:
        raise ValueError("cannot parse a None timestamp")
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, np.datetime64):
        dt = datetime.fromisoformat(np.datetime_as_string(value, unit="s"))
    else:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def time_offset_hours(profile_time: Any, granule_time: Any) -> float:
    """Absolute time offset ``|profile − granule|`` in hours."""
    delta = parse_time(profile_time) - parse_time(granule_time)
    return abs(delta.total_seconds()) / 3600.0


def footprint_bbox(wkt: Any) -> tuple[float, float, float, float] | None:
    """Bounding box ``(lon_min, lat_min, lon_max, lat_max)`` of a WKT footprint.

    A deliberately tolerant parser: it pulls the coordinate pairs out of any
    ``POLYGON``/``MULTIPOLYGON`` text (CMR gives simple swath quadrilaterals) and
    returns their extent.

    A footprint spanning more than 180° of longitude either crosses the
    antimeridian or is a high-latitude swath sweeping many meridians; for those
    the longitude bounds are widened to the full ``(-180, 180)`` and only the
    **latitude** band constrains the box — conservative, but still a real filter
    (a polar granule is never offered to a tropical float).

    Returns:
        The bounding box, or ``None`` when the footprint is missing or
        unparseable — which every caller reads as *"unknown, don't exclude"*.
    """
    if wkt is None:
        return None
    import re

    _num = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
    nums = [float(m) for m in re.findall(_num, str(wkt))]
    if len(nums) < 6 or len(nums) % 2:
        return None
    lons = np.asarray(nums[0::2], dtype=float)
    lats = np.asarray(nums[1::2], dtype=float)
    if np.any(np.abs(lats) > 90.0) or np.any(np.abs(lons) > 180.0):
        return None  # not a lon/lat pair list after all
    if float(lons.max() - lons.min()) > 180.0:
        # wraps the antimeridian (or sweeps meridians near a pole): keep the
        # latitude band, drop the longitude constraint
        return (-180.0, float(lats.min()), 180.0, float(lats.max()))
    return (float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max()))


def footprint_covers(
    bbox: tuple[float, float, float, float] | None,
    latitude: float,
    longitude: float,
    *,
    pad_deg: float = 0.0,
) -> bool:
    """Whether ``(latitude, longitude)`` falls in ``bbox`` padded by ``pad_deg``.

    An unknown ``bbox`` (``None``) returns ``True`` — the pre-filter never drops
    a granule it cannot place.
    """
    if bbox is None:
        return True
    lon_min, lat_min, lon_max, lat_max = bbox
    return (
        lat_min - pad_deg <= float(latitude) <= lat_max + pad_deg
        and lon_min - pad_deg <= float(longitude) <= lon_max + pad_deg
    )


class GranuleIndex:
    """In-memory time+footprint index over the ``granules`` table.

    Built **once per stage** and queried per profile, so candidate selection is
    ``O(log M)`` per profile instead of a full table scan (which, with the whole
    global granule set in the DB, made ``match`` quadratic in the run size).

    Times are parsed once; footprints are parsed once into bounding boxes
    (:func:`footprint_bbox`). :meth:`candidates` applies the temporal window
    **and** — when given a position — the spatial box, so a profile is only ever
    offered granules whose swath plausibly covers it (opening a granule is the
    expensive step: ~4.4 s in-cloud).
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        recs = []
        for row in rows:
            gtime = row.get("time_start")
            if gtime is None:
                continue
            try:
                t = parse_time(gtime)
            except ValueError:
                continue
            recs.append(
                (
                    t.timestamp(),
                    str(row["granule_id"]),
                    gtime,
                    row.get("data_url") or row["granule_id"],
                    footprint_bbox(row.get("footprint")),
                )
            )
        recs.sort(key=lambda r: r[0])
        self._epoch = np.array([r[0] for r in recs], dtype=float)
        self._recs = recs

    @classmethod
    def load(cls, store) -> GranuleIndex:
        """Build the index from every granule in ``store``."""
        return cls(
            store.query(
                "SELECT granule_id, time_start, footprint, data_url FROM granules"
            )
        )

    def __len__(self) -> int:
        return len(self._recs)

    def candidates(
        self,
        profile_time: Any,
        *,
        dtime_max_hours: float,
        latitude: float | None = None,
        longitude: float | None = None,
        pad_deg: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Granules within the time window (and, if given, over the position).

        Returns:
            Candidate dicts with ``granule_id``, ``time`` (``time_start``), and
            ``source`` (``data_url`` if present, else ``granule_id``) — the
            input :func:`find_matchup` expects.
        """
        if not self._recs:
            return []
        try:
            t0 = parse_time(profile_time).timestamp()
        except ValueError:
            return []
        half = float(dtime_max_hours) * 3600.0
        lo = int(np.searchsorted(self._epoch, t0 - half, side="left"))
        hi = int(np.searchsorted(self._epoch, t0 + half, side="right"))
        out: list[dict[str, Any]] = []
        for _, gid, gtime, source, bbox in self._recs[lo:hi]:
            if latitude is not None and longitude is not None:
                if not footprint_covers(bbox, latitude, longitude, pad_deg=pad_deg):
                    continue
            out.append({"granule_id": gid, "time": gtime, "source": source})
        return out


def _open_with_timeout(source, *, opener=None, timeout_s: float = 0.0):
    """Open a granule, raising :class:`TimeoutError` if it takes too long.

    Uses ``SIGALRM``, which interrupts the calling thread even when it is parked
    in a C-level lock — the state real wedged workers were found in (sockets no
    longer established, every thread in ``futex_wait``, 0 % CPU, no progress for
    40 min). ``fsspec``/``aiohttp`` provide no read timeout on this path, so this
    is the only reliable way to bound it.

    Falls back to a plain open when ``timeout_s`` is not positive, or when the
    caller is not the main thread (``signal.alarm`` is main-thread only) — the
    chunk-level guard in :func:`_build_matchups_parallel` remains the backstop
    for those cases.
    """
    import signal
    import threading

    if timeout_s and timeout_s > 0 and threading.current_thread() is threading.main_thread():

        def _timed_out(signum, frame):  # pragma: no cover - signal path
            raise TimeoutError(f"granule read exceeded {timeout_s:.0f}s: {source}")

        previous = signal.signal(signal.SIGALRM, _timed_out)
        signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
        try:
            return cloud.open_granule(source, opener=opener)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous)
    return cloud.open_granule(source, opener=opener)


def find_matchup(
    profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    opener=None,
    config: MatchupConfig | None = None,
) -> Matchup | None:
    """Select the best granule for a profile and extract its matchup pixels.

    Args:
        profile: Profile metadata — must include ``wmo``, ``cycle``,
            ``latitude``, ``longitude``, ``time`` (and ``profile_id`` if the
            result will be persisted).
        candidates: Candidate granules, each a dict with ``granule_id``,
            ``time`` (granule acquisition time), and ``source`` (the value
            passed to :func:`pab.pace.cloud.open_granule` / the ``opener``).
        opener: Optional override mapping ``source`` → canonical granule dataset
            (the test seam; mocks the cloud read).
        config: Matching criteria (defaults to :class:`MatchupConfig`).

    Returns:
        The best :class:`Matchup`, or ``None`` if no candidate qualifies in both
        time and space with at least one valid spectrum.

    Raises:
        ValueError: if the profile has no ``latitude``/``longitude``.
    """
    config = config or MatchupConfig()
    if profile.get("latitude") is None or profile.get("longitude") is None:
        raise ValueError(
            f"profile {profile.get('wmo')}/{profile.get('cycle')} has no "
            "latitude/longitude; cannot match it to a granule"
        )
    lat = float(profile["latitude"])
    lon = float(profile["longitude"])
    p_time = profile["time"]

    qualifying: list[dict[str, Any]] = []
    for g in candidates:
        dtime_hours = time_offset_hours(p_time, g["time"])
        if dtime_hours > config.dtime_max_hours:
            continue
        try:
            ds = _open_with_timeout(
                g["source"], opener=opener, timeout_s=config.open_timeout_s
            )
        except TimeoutError:
            # A dropped HTTPS connection can leave the read waiting forever (no
            # timeout in fsspec/aiohttp): observed as a worker with unestablished
            # sockets and every thread in futex_wait. Skip this granule and try
            # the profile's other candidates rather than losing the profile.
            _log.warning(
                "granule read timed out after %.0fs: %s",
                config.open_timeout_s,
                g["granule_id"],
            )
            continue
        pixels = _extract.extract_matchup_spectra(
            ds, lat, lon, n=config.n_spectra, mask_flags=config.mask_flags
        )
        if not pixels:
            continue  # no unflagged Rrs near the float in this granule
        distance_km = float(pixels[0]["distance_km"])
        if distance_km > config.max_distance_km:
            continue  # footprint does not actually cover the float
        for px in pixels:
            # selected pixels pass the screen, so the recorded result is 0
            px["flagged"] = int(
                bool(_flags.flagged_mask(np.array([px["flag"]]), config.mask_flags)[0])
            )
        qualifying.append(
            {
                "granule": g,
                "pixels": pixels,
                "distance_km": distance_km,
                "dtime_hours": dtime_hours,
                "n_spectra": len(pixels),
            }
        )

    if not qualifying:
        return None

    best = min(
        qualifying,
        key=lambda q: (
            q["distance_km"],
            q["dtime_hours"],
            -q["n_spectra"],
            str(q["granule"]["granule_id"]),
        ),
    )
    gid = str(best["granule"]["granule_id"])
    return Matchup(
        matchup_id=make_matchup_id(int(profile["wmo"]), int(profile["cycle"]), gid),
        granule_id=gid,
        distance_km=best["distance_km"],
        dtime_hours=best["dtime_hours"],
        n_spectra=best["n_spectra"],
        pixels=best["pixels"],
        profile_id=profile.get("profile_id"),
    )


def write_matchup(store, matchup: Matchup, *, created: str | None = None) -> str:
    """Persist a :class:`Matchup` (and its pixels) idempotently; return its id.

    Upserts the ``matchups`` row (stamped with ``pab_version`` + ``created``),
    then **replaces** the matchup's ``matchup_pixels`` (delete-then-insert) so a
    re-run leaves no stale or duplicate pixel rows.

    Args:
        store: An open :class:`pab.db.store.Store`.
        matchup: The matchup to write; ``profile_id`` must be set.
        created: Timestamp to stamp (defaults to now, UTC ISO-8601).

    Raises:
        ValueError: if ``matchup.profile_id`` is ``None``.
    """
    if matchup.profile_id is None:
        raise ValueError("Matchup.profile_id is required to persist the record")
    created = created or datetime.now(UTC).isoformat()

    store.upsert(
        "matchups",
        {
            "matchup_id": matchup.matchup_id,
            "profile_id": matchup.profile_id,
            "granule_id": matchup.granule_id,
            "distance_km": matchup.distance_km,
            "dtime_hours": matchup.dtime_hours,
            "n_spectra": matchup.n_spectra,
            "created": created,
            "pab_version": pab_version,
        },
    )
    store.execute(
        "DELETE FROM matchup_pixels WHERE matchup_id = ?", (matchup.matchup_id,)
    )
    store.upsert_many(
        "matchup_pixels",
        [
            {
                "matchup_id": matchup.matchup_id,
                "ix": int(px["ix"]),
                "iy": int(px["iy"]),
                "latitude": float(px["latitude"]),
                "longitude": float(px["longitude"]),
                "distance_km": float(px["distance_km"]),
                "rank": int(px["rank"]),
                "flagged": int(px.get("flagged", 0)),
            }
            for px in matchup.pixels
        ],
    )
    return matchup.matchup_id


def qualifying_profiles(store) -> list[dict[str, Any]]:
    """Profiles that have a mixed-layer summary (the matchup-eligible floats).

    Returns:
        One dict per profile with ``profile_id``, ``wmo``, ``cycle``,
        ``latitude``, ``longitude``, ``time`` — the inputs to
        :func:`find_matchup`.
    """
    return store.query(
        "SELECT p.profile_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time "
        "FROM profiles p JOIN mld_summary m ON p.profile_id = m.profile_id "
        "ORDER BY p.profile_id"
    )


def candidate_granules(
    store,
    profile_time: Any,
    *,
    dtime_max_hours: float,
    latitude: float | None = None,
    longitude: float | None = None,
    pad_deg: float = 0.0,
    index: GranuleIndex | None = None,
) -> list[dict[str, Any]]:
    """Candidate granules for a profile: temporal window + optional footprint.

    Granules whose start time is within ``dtime_max_hours`` of the profile and —
    when ``latitude``/``longitude`` are given — whose footprint bounding box
    (padded by ``pad_deg``) contains the float. The exact spatial test (the
    nearest unflagged pixel is within ``max_distance_km``) still happens in
    :func:`find_matchup` after the granule is opened; this only avoids opening
    granules that cannot possibly cover the float. Granules with an unparseable
    time, or a footprint that cannot be placed, are respectively skipped and
    kept.

    Args:
        store: An open store (ignored when ``index`` is supplied).
        profile_time: The profile timestamp.
        dtime_max_hours: Temporal half-window.
        latitude, longitude: Float position; omit for a time-only filter.
        pad_deg: Slack added to the footprint box.
        index: A prebuilt :class:`GranuleIndex` — pass one when querying many
            profiles (a stage), so the table is read and parsed **once**.

    Returns:
        Candidate dicts with ``granule_id``, ``time`` (``time_start``), and
        ``source`` (``data_url`` if present, else ``granule_id``).
    """
    idx = index if index is not None else GranuleIndex.load(store)
    return idx.candidates(
        profile_time,
        dtime_max_hours=dtime_max_hours,
        latitude=latitude,
        longitude=longitude,
        pad_deg=pad_deg,
    )


def build_matchups(
    store,
    *,
    opener=None,
    config: MatchupConfig | None = None,
    replace: bool = False,
    created: str | None = None,
    jobs: int = 1,
) -> dict[str, list[str]]:
    """Match every qualifying profile against the stored granules and persist.

    Idempotent and resumable: a matchup already in the DB (by ``matchup_id``) is
    skipped unless ``replace=True``.

    ``jobs > 1`` matches profiles **in parallel across processes** — each profile's
    granule opens + nearest-pixel extraction (the I/O- and CPU-heavy
    :func:`find_matchup`) run in a :class:`ProcessPoolExecutor`, while candidate
    lookups and **all DB writes stay in the parent** (single SQLite writer, no lock
    contention — the same design as the parallel ``fit`` stage). Workers are
    spawned, so an injected ``opener`` must be picklable (a module-level
    function); a closure/lambda opener silently runs the serial path instead.

    Args:
        store: An open :class:`pab.db.store.Store` (must already hold profiles +
            mixed-layer summaries and a ``granules`` candidate set).
        opener: Optional ``source`` → granule dataset override (test seam).
        config: Matching criteria (defaults to :class:`MatchupConfig`).
        replace: Re-write matchups that already exist.
        created: Timestamp to stamp on written rows.
        jobs: Profile-level parallel processes (1 = serial).

    Returns:
        ``{"written": [...], "skipped": [...], "unmatched": [...]}`` — matchup
        ids written, matchup ids skipped (already present), and
        ``"{wmo}_{cycle}"`` for profiles with no qualifying granule (or no
        position to match against).
    """
    config = config or MatchupConfig()
    written: list[str] = []
    skipped: list[str] = []
    unmatched: list[str] = []

    # Gather per-profile inputs in the parent (DB reads only); the heavy
    # open+extract in find_matchup is what fans out.
    inputs: list[tuple[dict, list[dict]]] = []
    index = GranuleIndex.load(store)  # read + parse the granule table once
    # Profiles already matched are skipped *before* any granule is opened. The
    # existence test used to happen only after find_matchup had done the work, so
    # a resumed match re-read every granule it had already processed (a restarted
    # 1000-profile run spent 15 min re-deriving matchups it already had; at 54k
    # that would dominate every restart).
    done: dict[int, str] = {}
    if not replace:
        for row in store.query("SELECT profile_id, matchup_id FROM matchups"):
            done.setdefault(row["profile_id"], row["matchup_id"])
    for profile in qualifying_profiles(store):
        if profile["profile_id"] in done:
            skipped.append(done[profile["profile_id"]])
            continue
        if profile["latitude"] is None or profile["longitude"] is None:
            # no position to match against — skip rather than raise mid-run
            unmatched.append(f"{profile['wmo']}_{profile['cycle']}")
            continue
        candidates = candidate_granules(
            store,
            profile["time"],
            dtime_max_hours=config.dtime_max_hours,
            latitude=profile["latitude"],
            longitude=profile["longitude"],
            pad_deg=config.footprint_pad_deg,
            index=index,
        )
        if not candidates:
            unmatched.append(f"{profile['wmo']}_{profile['cycle']}")
            continue
        inputs.append((profile, candidates))

    if jobs and int(jobs) > 1 and inputs and picklable(opener):
        return _build_matchups_parallel(
            store, inputs, config, created, int(jobs), replace,
            written, skipped, unmatched, opener=opener,
        )

    for profile, candidates in inputs:
        result = find_matchup(profile, candidates, opener=opener, config=config)
        if result is None:
            unmatched.append(f"{profile['wmo']}_{profile['cycle']}")
            continue
        exists = store.query(
            "SELECT 1 FROM matchups WHERE matchup_id = ?", (result.matchup_id,)
        )
        if exists and not replace:
            skipped.append(result.matchup_id)
            continue
        write_matchup(store, result, created=created)
        written.append(result.matchup_id)

    return {"written": written, "skipped": skipped, "unmatched": unmatched}


def _build_matchups_parallel(
    store, inputs, config, created, jobs, replace, written, skipped, unmatched,
    *, opener=None,
):
    """Parallel backend for :func:`build_matchups`. Mutates the result lists.

    ``find_matchup`` (open + extract + select) runs in worker processes; the
    parent drains completed futures and performs every DB write. ``opener`` is
    forwarded to the workers and must be picklable
    (see :func:`pab.parallel.picklable`).

    **Stall-proofed.** A granule read can wedge with no way back: on a real run
    every one of 16 workers ended up blocked on an in-process lock with *zero*
    open sockets and 0 % CPU after their S3 connections dropped, and the stage sat
    dead for 40 minutes. Neither ``fsspec`` nor HDF5 offers a timeout we can rely
    on there, so the parent enforces one: work goes out in **chunks with a fresh
    pool each**, and if a chunk produces no result at all within
    ``config.stall_timeout_s`` its remaining workers are killed, its profiles are
    recorded under ``"stalled"``, and the run moves to the next chunk. Stalled
    profiles keep no matchup, so a later resume simply retries them.
    """
    import multiprocessing as mp
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    # 'spawn' avoids fork-in-a-multithreaded-parent hazards; workers re-import
    # cleanly and find_matchup pickles by qualname.
    ctx = mp.get_context("spawn")
    fut_prof: dict = {}
    total = len(inputs)
    stalled: list[str] = []
    chunk_size = max(1, 4 * jobs)
    _log.info(
        "match: %d profiles over %d processes (chunks of %d, stall timeout %.0fs)",
        total,
        jobs,
        chunk_size,
        config.stall_timeout_s,
    )

    # Count only what this pool actually processes. Summing the result lists
    # would also count the profiles excluded before the pool ran (already
    # matched, or no candidate granules), which pushed the log to nonsense like
    # "900/589".
    done_count = 0

    def _progress() -> None:
        if done_count % PROGRESS_EVERY == 0:
            _log.info(
                "match progress: %d/%d processed (%d written, %d unmatched; "
                "%d pre-skipped)",
                done_count,
                total,
                len(written),
                done_count - len(written),
                len(skipped),
            )

    def _bump() -> None:
        nonlocal done_count
        done_count += 1
        _progress()

    def _drain(fut):
        profile = fut_prof.pop(fut)
        pid = f"{profile['wmo']}_{profile['cycle']}"
        try:
            result = fut.result()
        except Exception:  # noqa: BLE001 — one bad profile must not abort the batch
            _log.exception("match failed for %s", pid)
            unmatched.append(pid)
            _bump()
            return
        if result is None:
            unmatched.append(pid)
            _bump()
            return
        exists = store.query(
            "SELECT 1 FROM matchups WHERE matchup_id = ?", (result.matchup_id,)
        )
        if exists and not replace:
            skipped.append(result.matchup_id)
        else:
            write_matchup(store, result, created=created)
            written.append(result.matchup_id)
        _bump()

    for start in range(0, total, chunk_size):
        chunk = inputs[start : start + chunk_size]
        ex = ProcessPoolExecutor(
            max_workers=jobs, mp_context=ctx, initializer=init_worker
        )
        pending = set()
        for profile, candidates in chunk:
            fut = ex.submit(
                find_matchup, profile, candidates, opener=opener, config=config
            )
            fut_prof[fut] = profile
            pending.add(fut)
        while pending:
            done, pending = wait(
                pending,
                timeout=config.stall_timeout_s,
                return_when=FIRST_COMPLETED,
            )
            if not done:  # nothing at all finished in the window -> wedged
                for fut in pending:
                    profile = fut_prof.pop(fut)
                    stalled.append(f"{profile['wmo']}_{profile['cycle']}")
                _log.error(
                    "match stalled after %.0fs with %d profiles in flight; "
                    "killing the pool and continuing (they stay unmatched and are "
                    "retried on the next run)",
                    config.stall_timeout_s,
                    len(pending),
                )
                _kill_pool(ex)
                pending = set()
                break
            for f in done:
                _drain(f)
        ex.shutdown(wait=False, cancel_futures=True)

    if stalled:
        _log.error("match: %d profiles stalled in total", len(stalled))
    return {
        "written": written,
        "skipped": skipped,
        "unmatched": unmatched,
        "stalled": stalled,
    }


def _kill_pool(ex) -> None:
    """Hard-stop a wedged :class:`ProcessPoolExecutor`'s workers.

    ``shutdown(cancel_futures=True)`` only drops *queued* work — a worker already
    blocked inside a C-level lock keeps the interpreter alive, so the processes
    have to be killed outright. Uses the executor's process map when available
    (private, but there is no public equivalent) and falls back to this process's
    children.
    """
    import multiprocessing as mp

    procs = list(getattr(ex, "_processes", {}).values()) or mp.active_children()
    for proc in procs:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001 — best effort; already-dead is fine
            pass
