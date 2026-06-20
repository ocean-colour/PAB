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

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from pab.config import pab_version
from pab.pace import cloud
from pab.pace import extract as _extract
from pab.pace import flags as _flags

__all__ = [
    "MatchupConfig",
    "Matchup",
    "make_matchup_id",
    "parse_time",
    "time_offset_hours",
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
    """

    dtime_max_hours: float = 24.0
    n_spectra: int = 10
    max_distance_km: float = 5.0
    mask_flags: tuple[str, ...] = field(default=_flags.STANDARD_OCEAN_MASK)


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
    """
    config = config or MatchupConfig()
    lat = float(profile["latitude"])
    lon = float(profile["longitude"])
    p_time = profile["time"]

    qualifying: list[dict[str, Any]] = []
    for g in candidates:
        dtime_hours = time_offset_hours(p_time, g["time"])
        if dtime_hours > config.dtime_max_hours:
            continue
        ds = cloud.open_granule(g["source"], opener=opener)
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
    store, profile_time: Any, *, dtime_max_hours: float
) -> list[dict[str, Any]]:
    """Granules whose start time is within ``dtime_max_hours`` of the profile.

    A cheap temporal pre-filter over the ``granules`` table; the spatial test
    (the float falls within the footprint) is applied in :func:`find_matchup`
    after the granule is opened. Granules with an unparseable time are skipped.

    Returns:
        Candidate dicts with ``granule_id``, ``time`` (``time_start``), and
        ``source`` (``data_url`` if present, else ``granule_id``).
    """
    out: list[dict[str, Any]] = []
    for row in store.query("SELECT granule_id, time_start, data_url FROM granules"):
        gtime = row["time_start"]
        if gtime is None:
            continue
        try:
            if time_offset_hours(profile_time, gtime) > dtime_max_hours:
                continue
        except ValueError:
            continue
        out.append(
            {
                "granule_id": row["granule_id"],
                "time": gtime,
                "source": row["data_url"] or row["granule_id"],
            }
        )
    return out


def build_matchups(
    store,
    *,
    opener=None,
    config: MatchupConfig | None = None,
    replace: bool = False,
    created: str | None = None,
) -> dict[str, list[str]]:
    """Match every qualifying profile against the stored granules and persist.

    Idempotent and resumable: a matchup already in the DB (by ``matchup_id``) is
    skipped unless ``replace=True``.

    Args:
        store: An open :class:`pab.db.store.Store` (must already hold profiles +
            mixed-layer summaries and a ``granules`` candidate set).
        opener: Optional ``source`` → granule dataset override (test seam).
        config: Matching criteria (defaults to :class:`MatchupConfig`).
        replace: Re-write matchups that already exist.
        created: Timestamp to stamp on written rows.

    Returns:
        ``{"written": [...], "skipped": [...], "unmatched": [...]}`` — matchup
        ids written, matchup ids skipped (already present), and
        ``"{wmo}_{cycle}"`` for profiles with no qualifying granule.
    """
    config = config or MatchupConfig()
    written: list[str] = []
    skipped: list[str] = []
    unmatched: list[str] = []

    for profile in qualifying_profiles(store):
        candidates = candidate_granules(
            store, profile["time"], dtime_max_hours=config.dtime_max_hours
        )
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
