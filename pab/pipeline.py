"""End-to-end pipeline & CLI (Stage 8).

A single, resumable, config-driven stage runner tying Stages 2–7 together —
**ingest → discover → match → fit → figure → report** — with **no new science**:
each stage is a thin wrapper over the module already built for it, reads/writes
the shared :class:`pab.db.store.Store`, and **skips work already done** (the
existing `persist_*`/`build_*` idempotency), so a re-run resumes. Re-running
under a new ``pab_version`` adds records rather than overwriting.

The network/heavy seams stay **injectable** — ``fetcher`` (argopy), ``searcher``
(earthaccess discovery), and ``opener`` (:func:`pab.pace.cloud.open_granule`) —
so the pipeline runs offline on synthetic inputs in tests while the orchestration
(stage order, skip/resume, the run summary) is plain, testable code.
"""

from __future__ import annotations

import argparse
import inspect
import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from pab.config import DATA_DIR
from pab.config import pab_version as _pab_version
from pab.fit.models import FitConfig
from pab.matchup.engine import MatchupConfig
from pab.parallel import PROGRESS_EVERY, init_worker, picklable

_log = logging.getLogger("pab.pipeline")

#: The pipeline stages, in run order.
STAGES: tuple[str, ...] = ("ingest", "discover", "match", "fit", "figure", "report")


@dataclass
class PipelineConfig:
    """Configuration for an end-to-end pipeline run.

    Attributes:
        profiles: Inline profile dicts (offline) — each ``{wmo, cycle, latitude,
            longitude, time}`` and optionally a precomputed ``summary`` (then
            ``ingest`` persists it directly instead of fetching).
        profiles_csv: Path to a dev-set CSV (default ``data/dev_profiles.csv``)
            used when ``profiles`` is ``None``.
        argo_src, argo_mode: argopy source/mode for the live fetch.
        short_name: PACE collection short name for discovery.
        bbox_pad_deg, dtime_days, cloud_cover: granule-discovery window.
        matchup, fit: the Stage-4 / Stage-5 configs.
        outdir: base output directory (defaults to ``DATA_DIR/pipeline``).
        make_figures: render per-matchup figures in the ``figure`` stage.
        replace: re-do already-completed work (else stages skip it).
        download: pre-download granules to ``cache_dir`` and read them locally
            (the reliable off-cloud path) instead of lazy out-of-region S3/HTTPS.
        cache_dir: where downloaded granules live (defaults to ``DATA_DIR/granules``).
        jobs: worker processes for the ``match`` and ``fit`` stages.
        ingest_jobs: concurrent argopy fetches in ``ingest``. ``None`` derives it
            from ``jobs`` — see :meth:`ingest_workers`.
    """

    profiles: list[dict[str, Any]] | None = None
    profiles_csv: str | Path | None = None
    argo_src: str = "gdac"
    argo_mode: str = "expert"
    short_name: str = "PACE_OCI_L2_AOP"
    bbox_pad_deg: float = 0.4
    dtime_days: float = 1.0
    cloud_cover: tuple[int, int] = (0, 100)
    matchup: MatchupConfig = field(default_factory=MatchupConfig)
    fit: FitConfig = field(default_factory=FitConfig)
    outdir: str | Path | None = None
    make_figures: bool = True
    replace: bool = False
    download: bool = False
    cache_dir: str | Path | None = None
    jobs: int = 1  # parallel processes for the match + fit stages (1 = serial)
    ingest_jobs: int | None = None  # concurrent argopy fetches (None → derived)
    discover_jobs: int | None = None  # concurrent CMR searches (None → derived)

    #: Ceiling on concurrent argopy fetches when ``ingest_jobs`` is derived from
    #: ``jobs``. The Argo GDAC/ERDDAP servers are shared infrastructure, so a
    #: 50-core run must not open 50 simultaneous fetches.
    INGEST_JOBS_CAP: ClassVar[int] = 16

    #: Ceiling on concurrent CMR searches. NASA's CMR is shared too, and 8 threads
    #: already turned a 26 h serial stage into ~2 h in the one-off count script.
    DISCOVER_JOBS_CAP: ClassVar[int] = 8

    def out(self) -> Path:
        """The resolved base output directory."""
        return Path(self.outdir) if self.outdir else Path(DATA_DIR) / "pipeline"

    def cache(self) -> Path:
        """The resolved granule download cache directory."""
        return Path(self.cache_dir) if self.cache_dir else Path(DATA_DIR) / "granules"

    def ingest_workers(self) -> int:
        """Concurrent argopy fetches for ``ingest``.

        ``ingest_jobs`` when set, else ``jobs`` capped at
        :attr:`INGEST_JOBS_CAP` — so ``--jobs 50`` (sized for the CPU-bound
        ``match``/``fit`` stages) does not translate into 50 simultaneous
        requests to the shared Argo servers.
        """
        if self.ingest_jobs is not None:
            return max(1, int(self.ingest_jobs))
        return max(1, min(int(self.jobs), self.INGEST_JOBS_CAP))

    def discover_workers(self) -> int:
        """Concurrent CMR searches for ``discover`` (threads).

        ``discover_jobs`` when set, else ``jobs`` capped at
        :attr:`DISCOVER_JOBS_CAP` — CMR is shared NASA infrastructure.
        """
        if self.discover_jobs is not None:
            return max(1, int(self.discover_jobs))
        return max(1, min(int(self.jobs), self.DISCOVER_JOBS_CAP))

    def selection_keys(self) -> set[tuple[int, int]] | None:
        """``{(wmo, cycle)}`` of an **explicitly requested** selection, else ``None``.

        ``None`` means "no selection was given" — distinct from an empty one — so a
        bare ``pab --stage discover`` keeps working over every profile in the store
        rather than silently narrowing to the default dev CSV.
        """
        if self.profiles is None and self.profiles_csv is None:
            return None
        return {(int(r["wmo"]), int(r["cycle"])) for r in self.profile_rows()}

    def profile_rows(self) -> list[dict[str, Any]]:
        """The profile selection — inline ``profiles`` or the dev-set CSV rows."""
        if self.profiles is not None:
            return list(self.profiles)
        import pandas as pd

        csv = Path(self.profiles_csv) if self.profiles_csv else _default_dev_csv()
        return pd.read_csv(csv).to_dict(orient="records")


def _default_dev_csv() -> Path:
    from pab.config import ROOT

    return Path(ROOT) / "data" / "dev_profiles.csv"


# -- stages -----------------------------------------------------------------
def ingest(store, config: PipelineConfig, *, fetcher=None) -> dict[str, Any]:
    """Persist BGC-Argo profiles + mixed-layer summaries (idempotent).

    For each selected profile: if it already has an ``mld_summary`` (and not
    ``replace``), skip. Otherwise persist a precomputed ``summary`` (offline) or
    fetch + summarize via argopy (``fetcher`` overrides the live fetch — it takes
    ``(wmo, cycle, argo_src, argo_mode)`` and returns an argopy dataset).

    The live fetch dominates the stage (~6 s/profile serial — days over the full
    selection), so with :meth:`PipelineConfig.ingest_workers` > 1 the
    fetch+summarize step fans out (:func:`_ingest_executor`) while **every DB
    write and Q&A plot stays in the parent** — one SQLite writer, matplotlib off
    the workers. Failures stay per-profile: a bad profile is recorded under
    ``"failed"`` (with a traceback in the ``pab.pipeline`` log) and the stage
    carries on, so a resume retries only what is missing.
    """
    written, skipped, failed = [], [], []

    # One query for every already-summarized (wmo, cycle), not one per CSV row.
    # SQLite on CephFS costs ~200 ms per round trip, so the per-row version spent
    # ~3 h building this list for the 54,506-profile selection before fetching a
    # single profile — and paid it again on every resume.
    have: set[tuple[int, int]] = set()
    if not config.replace:
        have = {
            (int(r["wmo"]), int(r["cycle"]))
            for r in store.query(
                "SELECT p.wmo, p.cycle FROM mld_summary ms "
                "JOIN profiles p ON p.profile_id = ms.profile_id"
            )
        }

    todo: list[tuple[int, int, dict[str, Any]]] = []
    for row in config.profile_rows():
        wmo, cycle = int(row["wmo"]), int(row["cycle"])
        if (wmo, cycle) in have:
            skipped.append(f"{wmo}_{cycle}")
            continue
        todo.append((wmo, cycle, row))

    workers = config.ingest_workers()
    n_fetch = sum(1 for _, _, row in todo if "summary" not in row)
    if workers > 1 and n_fetch > 1:
        _ingest_concurrent(store, config, todo, fetcher, workers, written, failed)
        return {"written": written, "skipped": skipped, "failed": failed}

    for wmo, cycle, row in todo:
        # A single bad profile (odd argopy return, a 0-d array, a fetch error) must
        # not abort a 50k-profile ingest — record it and resume, like build_fits.
        try:
            _persist_profile(
                store,
                config,
                wmo,
                cycle,
                row,
                _fetch_profile_payload(config, wmo, cycle, row, fetcher),
            )
            written.append(f"{wmo}_{cycle}")
        except Exception:  # noqa: BLE001 — one bad profile must not abort the batch
            failed.append(f"{wmo}_{cycle}")
    return {"written": written, "skipped": skipped, "failed": failed}


def _fetch_profile_payload(
    config: PipelineConfig, wmo: int, cycle: int, row: dict[str, Any], fetcher
) -> dict[str, Any] | None:
    """Fetch + summarize one profile — **no DB access** (safe off-thread).

    Returns ``None`` for the offline path (``row`` already carries a
    precomputed ``summary``), else the ``meta``/``summary``/profile arrays that
    :func:`_persist_profile` writes.
    """
    if "summary" in row:
        return None
    from pab.argo import fetch, summary

    ds = (
        fetcher(wmo, cycle, config.argo_src, config.argo_mode)
        if fetcher is not None
        else fetch.fetch_profile(wmo, cycle, src=config.argo_src, mode=config.argo_mode)
    )
    meta, v = next(fetch.iter_profiles(ds))
    summ = summary.summarize_profile(
        v["PRES"],
        bbp700=v.get("BBP700"),
        chla=v.get("CHLA"),
        psal=v.get("PSAL"),
        temp=v.get("TEMP"),
        lon=meta["longitude"],
        lat=meta["latitude"],
    )
    return {"meta": meta, "summary": summ, "v": v}


def _persist_profile(
    store,
    config: PipelineConfig,
    wmo: int,
    cycle: int,
    row: dict[str, Any],
    payload: dict[str, Any] | None,
) -> None:
    """Write one profile's summary (+ Q&A figure). Caller's thread only."""
    from pab.argo import summary

    if payload is None:  # offline: a precomputed summary
        summary.persist_summary(
            store,
            wmo=wmo,
            cycle=cycle,
            summary=row["summary"],
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
            time=row.get("time"),
        )
        return

    meta, summ, v = payload["meta"], payload["summary"], payload["v"]
    pid = summary.persist_summary(
        store,
        wmo=wmo,
        cycle=cycle,
        summary=summ,
        latitude=meta["latitude"],
        longitude=meta["longitude"],
        time=meta["time"],
    )
    # Q&A figure: only the live fetch carries the full profile arrays the plot
    # needs (the precomputed-summary path has scalars only).
    _emit_profile_qa(
        store,
        pid,
        wmo,
        cycle,
        config,
        pres=v["PRES"],
        bbp700=v.get("BBP700"),
        chla=v.get("CHLA"),
        mld=summ.get("mld"),
    )


def _ingest_executor(fetcher, workers: int):
    """The pool :func:`_ingest_concurrent` should use, and a label for logs.

    **Processes** for the live path. Measured on real GDAC profiles: serial
    6.2 s/profile, 12 threads 2.75, **12 processes 0.97** — the fetch is not
    network-bound but bound by argopy's Python-side parsing, so the GIL, not the
    servers, is the ceiling. Processes need a picklable ``fetcher``
    (``None`` = the live fetch, or a module-level seam); anything else (a
    lambda/closure test seam) falls back to **threads**, which still concurrent
    the I/O and keeps the datasets in-process.
    """
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    if picklable(fetcher):
        return (
            ProcessPoolExecutor(
                max_workers=workers,
                mp_context=mp.get_context("spawn"),
                initializer=init_worker,
            ),
            "processes",
        )
    return ThreadPoolExecutor(max_workers=workers), "threads"


def _ingest_concurrent(
    store, config: PipelineConfig, todo, fetcher, workers: int, written, failed
) -> None:
    """Concurrent backend for :func:`ingest`; appends to ``written``/``failed``.

    Fetch + summarize fan out (see :func:`_ingest_executor` for process vs
    thread); **every DB write and Q&A plot happens here in the parent** — one
    SQLite writer, matplotlib off the workers. In-flight fetches are bounded at
    ~2×``workers``, so a 54k-profile ingest holds only a handful of profiles in
    memory and persists results as they arrive (an interrupted run keeps
    everything already written; a resume re-fetches only what is missing).
    """
    from concurrent.futures import FIRST_COMPLETED, wait

    # Workers only need the argopy source/mode; don't ship an inline profile
    # list (offline seam) to every task.
    task_config = replace(config, profiles=None)

    def _drain(fut, pending_map):
        wmo, cycle, row = pending_map.pop(fut)
        try:
            _persist_profile(store, config, wmo, cycle, row, fut.result())
            written.append(f"{wmo}_{cycle}")
        except Exception:  # noqa: BLE001 — one bad profile must not abort the batch
            _log.exception("ingest failed for %s_%s", wmo, cycle)
            failed.append(f"{wmo}_{cycle}")
        done = len(written) + len(failed)
        if done % PROGRESS_EVERY == 0:
            _log.info(
                "ingest progress: %d/%d (%d written, %d failed)",
                done,
                len(todo),
                len(written),
                len(failed),
            )

    fut_row: dict = {}
    pending: set = set()
    executor, kind = _ingest_executor(fetcher, workers)
    _log.info("ingest: %d profiles over %d %s", len(todo), workers, kind)
    with executor as ex:
        for wmo, cycle, row in todo:
            fut = ex.submit(
                _fetch_profile_payload, task_config, wmo, cycle, row, fetcher
            )
            fut_row[fut] = (wmo, cycle, row)
            pending.add(fut)
            if len(pending) >= 2 * workers:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in done:
                    _drain(f, fut_row)
        for f in wait(pending).done:
            _drain(f, fut_row)


def _emit_profile_qa(
    store, profile_id, wmo, cycle, config: PipelineConfig, *, pres, bbp700, chla, mld
) -> None:
    """Best-effort Argo Q&A figure for a freshly-fetched profile.

    Renders ``BBP700``/``CHLA`` vs pressure (MLD marked) to
    ``config.out()/argo_qa/<wmo>_<cycle>.png`` and records the path in
    ``mld_summary.qa_path`` so the report can surface it. Gated on
    ``config.make_figures`` and fully guarded — a plotting failure (or no
    plottable variable) must never abort ``ingest``.
    """
    if not config.make_figures:
        return
    try:
        from pab.argo import qa

        qadir = config.out() / "argo_qa"
        qadir.mkdir(parents=True, exist_ok=True)
        path = qadir / f"{wmo}_{cycle}.png"
        qa.save_profile_qa(
            path,
            pres,
            bbp700=bbp700,
            chla=chla,
            mld=mld,
            title=f"WMO {wmo} / cycle {cycle}",
        )
        store.execute(
            "UPDATE mld_summary SET qa_path = ? WHERE profile_id = ?",
            (str(path), profile_id),
        )
    except Exception:  # noqa: BLE001 — the Q&A plot is a bonus artifact
        pass


def discover(store, config: PipelineConfig, *, searcher=None) -> dict[str, Any]:
    """Discover + persist PACE granules around each profile (idempotent upsert).

    Operates on the profiles in the store, narrowed to ``profiles``/
    ``profiles_csv`` when one is given explicitly (see
    :meth:`PipelineConfig.selection_keys`) — that is what makes a targeted
    re-search of a subset possible without re-doing the whole selection.

    ``searcher(lat, lon, t0, t1, config)`` overrides the live earthaccess search
    (it returns a granule ``DataFrame``); otherwise ``pab.pace.discover`` is used.
    A profile that already has granules **over its own position** in its time
    window is **skipped** (no re-query) unless ``replace`` — so a resume doesn't
    re-hit the network. The position test matters: granules found for a profile
    on the other side of the planet share its time window but say nothing about
    this profile's coverage (skipping on time alone silently starved most
    profiles of granules once the table held many).

    Per-profile failures are **contained**: a search that still fails after
    :func:`_search_with_retry`'s attempts is recorded under ``"failed"`` and the
    stage carries on (a single unhandled CMR error used to abort the whole
    stage — it truncated the 1000-profile run at 130 granules).
    """
    from pab.matchup.engine import GranuleIndex, candidate_granules
    from pab.pace import discover as disc

    profiles = store.query(
        "SELECT wmo, cycle, latitude, longitude, time FROM profiles "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    # Restrict to the requested selection when one was given explicitly. Without
    # this the stage always swept the whole store, so a targeted re-search (e.g.
    # the 10,101 profiles the coverage test skipped in the full run) meant
    # re-doing all 53,618.
    selection = config.selection_keys()
    if selection is not None:
        profiles = [
            p for p in profiles if (int(p["wmo"]), int(p["cycle"])) in selection
        ]
        _log.info(
            "discover: selection restricts to %d of the store's profiles",
            len(profiles),
        )
    n, skipped, failed, searched = 0, [], [], 0
    dtime_hours = config.dtime_days * 24.0
    # Snapshot the granule table once: granules persisted during this pass are
    # not in the index, so at worst a shared granule is re-queried (an idempotent
    # upsert) — never a missed search.
    index = GranuleIndex.load(store)
    todo: list[dict[str, Any]] = []
    for p in profiles:
        if not config.replace and candidate_granules(
            store,
            p["time"],
            dtime_max_hours=dtime_hours,
            latitude=p["latitude"],
            longitude=p["longitude"],
            # pad 0 here on purpose: skip a search only on *solid* evidence that
            # this profile is already covered. (match, by contrast, pads the box
            # generously — opening a granule that turns out not to cover the
            # float only costs time, whereas a skipped search loses it for good.)
            pad_deg=0.0,
            index=index,
        ):
            skipped.append(f"{p['wmo']}_{p['cycle']}")
            continue
        todo.append(p)

    def _persist(p, table) -> None:
        """Parent-side: record a completed search. Returns nothing."""
        nonlocal n, searched
        if table is not None and len(table):
            n += disc.persist_granules(store, table, short_name=config.short_name)
        searched += 1
        if searched % PROGRESS_EVERY == 0:
            _log.info(
                "discover progress: %d searched, %d granules, %d skipped, %d failed",
                searched,
                n,
                len(skipped),
                len(failed),
            )

    workers = config.discover_workers()
    if workers > 1 and len(todo) > 1:
        _discover_concurrent(config, todo, searcher, workers, _persist, failed)
    else:
        for p in todo:
            try:
                table = _search_profile(config, p, searcher)
            except Exception:  # noqa: BLE001 — one bad search must not abort the stage
                _log.exception("discover failed for %s_%s", p["wmo"], p["cycle"])
                failed.append(f"{p['wmo']}_{p['cycle']}")
                continue
            _persist(p, table)
    _log.info(
        "discover done: %d granules from %d searches (%d skipped, %d failed)",
        n,
        searched,
        len(skipped),
        len(failed),
    )
    return {"granules_upserted": n, "skipped": skipped, "failed": failed}


def _search_profile(config: PipelineConfig, profile, searcher):
    """One profile's granule search (CMR or the injected seam). No DB access.

    Safe to call from a worker thread: it only computes the window/bbox and issues
    the query, so the parent keeps sole ownership of the store.
    """
    from pab.pace import discover as disc

    t = datetime.fromisoformat(str(profile["time"]))
    t0 = t - timedelta(days=config.dtime_days)
    t1 = t + timedelta(days=config.dtime_days)
    lat, lon = profile["latitude"], profile["longitude"]
    if searcher is not None:
        return _search_with_retry(searcher, lat, lon, t0, t1, config)

    def _live(lat, lon, t0, t1, cfg, _disc=disc):
        return _disc.granule_table(
            _disc.search_granules(
                short_name=cfg.short_name,
                temporal=(t0.isoformat(), t1.isoformat()),
                bounding_box=search_bbox(lon, lat, cfg.bbox_pad_deg),
                cloud_cover=cfg.cloud_cover,
            )
        )

    return _search_with_retry(_live, lat, lon, t0, t1, config)


def _discover_concurrent(config, todo, searcher, workers, persist, failed) -> None:
    """Run the granule searches concurrently; ``persist`` runs in this thread.

    CMR queries are pure network latency — the one-off full-selection count did
    54.5k of them in 1.7 h with 8 threads, against ~1.75 s each serially (26 h for
    the full run). Threads (not processes) because nothing needs to be picklable
    and the GIL is irrelevant while waiting on HTTP. Every DB write stays here in
    the parent; in-flight searches are bounded at ~4x workers.
    """
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    fut_prof: dict = {}
    pending: set = set()
    _log.info("discover: %d searches over %d threads", len(todo), workers)

    def _drain(fut):
        profile = fut_prof.pop(fut)
        try:
            persist(profile, fut.result())
        except Exception:  # noqa: BLE001 — one bad search must not abort the stage
            _log.exception(
                "discover failed for %s_%s", profile["wmo"], profile["cycle"]
            )
            failed.append(f"{profile['wmo']}_{profile['cycle']}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for profile in todo:
            fut = ex.submit(_search_profile, config, profile, searcher)
            fut_prof[fut] = profile
            pending.add(fut)
            if len(pending) >= 4 * workers:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in done:
                    _drain(f)
        for f in wait(pending).done:
            _drain(f)


def search_bbox(
    longitude: float, latitude: float, pad_deg: float
) -> tuple[float, float, float, float]:
    """A CMR-legal ``(west, south, east, north)`` box around a float position.

    CMR **rejects** a box outside ``[-180, 180] × [-90, 90]``
    (``"West must be within [-180.0] and [180.0] but was [-180.2566]"`` — a float
    at lon −179.86 with the default 0.4° pad, which aborted the 1000-profile
    run's ``discover`` stage). Clamping is safe rather than lossy: the box still
    contains the float, so any granule whose swath covers the float still
    intersects it.
    """
    return (
        max(-180.0, float(longitude) - pad_deg),
        max(-90.0, float(latitude) - pad_deg),
        min(180.0, float(longitude) + pad_deg),
        min(90.0, float(latitude) + pad_deg),
    )


def _search_with_retry(searcher, lat, lon, t0, t1, config, *, attempts: int = 3):
    """Call ``searcher`` with retries for transient CMR failures.

    CMR returns intermittent 5xx/timeouts at scale (the full-selection
    discover-count saw ~1.7 % fail). Retrying a couple of times with a short
    backoff converts most of those into successes; the caller records whatever
    still fails.
    """
    import time

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return searcher(lat, lon, t0, t1, config)
        except Exception as exc:  # noqa: BLE001 — retry any search failure
            last = exc
            if attempt < attempts - 1:
                time.sleep(2**attempt)
    raise last  # type: ignore[misc]


def match(store, config: PipelineConfig, *, opener=None) -> dict[str, Any]:
    """Stage 4: build matchups (idempotent/resumable)."""
    from pab.matchup.engine import build_matchups

    return build_matchups(
        store,
        opener=opener,
        config=config.matchup,
        replace=config.replace,
        jobs=config.jobs,
    )


def fit(store, config: PipelineConfig, *, opener=None) -> dict[str, Any]:
    """Stage 5: fit each matchup with BING (idempotent by ``fit_id``)."""
    from pab.fit.run import build_fits

    return build_fits(
        store,
        opener=opener,
        config=config.fit,
        replace=config.replace,
        jobs=config.jobs,
    )


def figure(store, config: PipelineConfig, *, opener=None) -> dict[str, Any]:
    """Stage 6: render per-matchup fit + scene figures; record ``figure_path``.

    Best-effort per fit (a failed render is recorded, not fatal). Skips fits that
    already have a ``figure_path`` unless ``replace``.

    Rendering is the **most expensive stage per matchup** — 42 s measured in-pod,
    because each fit figure reconstructs the posterior and each scene re-opens the
    granule. With ``jobs > 1`` the renders run in worker processes
    (:func:`_render_figure`); the parent records the paths, so it stays the only
    DB writer.
    """
    if not config.make_figures:
        return {"written": [], "skipped": [], "failed": []}

    figdir = config.out() / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    written, skipped, failed = [], [], []
    todo: list[tuple[str, str]] = []
    for r in store.query(
        "SELECT fit_id, matchup_id, figure_path FROM fits ORDER BY fit_id"
    ):
        if r["figure_path"] and not config.replace:
            skipped.append(r["fit_id"])
            # Cheap backfill: record an already-rendered scene (no re-render, no
            # bing/granule), so existing runs surface scenes without --replace.
            sp = figdir / f"{r['matchup_id']}_scene.png"
            if sp.is_file():
                store.execute(
                    "UPDATE matchups SET scene_path = ? "
                    "WHERE matchup_id = ? AND scene_path IS NULL",
                    (str(sp), r["matchup_id"]),
                )
            continue
        todo.append((r["fit_id"], r["matchup_id"]))

    def _record(fit_id: str, matchup_id: str, paths) -> None:
        fpath, scene_path = paths
        store.execute(
            "UPDATE fits SET figure_path = ? WHERE fit_id = ?", (str(fpath), fit_id)
        )
        if scene_path is not None:
            store.execute(
                "UPDATE matchups SET scene_path = ? WHERE matchup_id = ?",
                (str(scene_path), matchup_id),
            )
        written.append(fit_id)

    db_path = _store_path(store)
    if int(config.jobs) > 1 and todo and db_path and picklable(opener):
        _figures_parallel(
            config, todo, figdir, opener, int(config.jobs), _record, failed, db_path
        )
        return {"written": written, "skipped": skipped, "failed": failed}

    for fit_id, matchup_id in todo:
        try:
            _record(
                fit_id,
                matchup_id,
                _render_figure(None, fit_id, matchup_id, figdir, opener, store=store),
            )
        except Exception:  # noqa: BLE001 — one bad render must not abort the batch
            _log.exception("figure failed for %s", fit_id)
            failed.append(fit_id)
    return {"written": written, "skipped": skipped, "failed": failed}


def _store_path(store) -> str | None:
    """Filesystem path behind ``store``, or ``None`` for an in-memory DB.

    Workers open their own connection to the same file, so a ``:memory:`` store
    (the test/offline case) cannot be shared and must render serially.
    """
    try:
        for row in store.query("PRAGMA database_list"):
            if row.get("name") == "main":
                return row.get("file") or None
    except Exception:  # noqa: BLE001 — treat any oddity as "not shareable"
        return None
    return None


def _render_figure(db_path, fit_id, matchup_id, figdir, opener, *, store=None):
    """Render one fit figure (+ its scene); return ``(fig_path, scene_path)``.

    Runs in a worker process when ``db_path`` is given: it opens its **own**
    connection with ``create=False`` — no schema migration, hence no write — so
    the parent remains the single writer while N workers read concurrently.
    ``store`` is the parent's connection for the serial path.
    """
    from pathlib import Path as _Path

    from pab.plotting import fit_fig, scene

    figdir = _Path(figdir)
    own = store is None
    if own:
        from pab.db import Store

        store = Store.open(db_path, create=False)
    try:
        fpath = figdir / f"{fit_id}_fit.png"
        fit_fig.fit_figure(store, fit_id, outfile=fpath)
        scene_path = None
        try:  # the scene is a bonus artifact; don't fail the fit figure on it
            scene_path = scene.scene_from_store(
                store,
                matchup_id,
                opener=opener,
                outfile=figdir / f"{matchup_id}_scene.png",
            )
        except Exception:  # noqa: BLE001
            pass
        return str(fpath), (str(scene_path) if scene_path is not None else None)
    finally:
        if own:
            store.close()


def _figures_parallel(
    config, todo, figdir, opener, jobs, record, failed, db_path
) -> None:
    """Render ``todo`` across worker processes; ``record`` writes in the parent."""
    import multiprocessing as mp
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    fut_row: dict = {}
    pending: set = set()
    _log.info("figure: rendering %d fits over %d processes", len(todo), jobs)

    def _drain(fut):
        fit_id, matchup_id = fut_row.pop(fut)
        try:
            record(fit_id, matchup_id, fut.result())
        except Exception:  # noqa: BLE001 — one bad render must not abort the batch
            _log.exception("figure failed for %s", fit_id)
            failed.append(fit_id)

    with ProcessPoolExecutor(
        max_workers=jobs, mp_context=mp.get_context("spawn"), initializer=init_worker
    ) as ex:
        for i, (fit_id, matchup_id) in enumerate(todo, start=1):
            fut = ex.submit(
                _render_figure, db_path, fit_id, matchup_id, str(figdir), opener
            )
            fut_row[fut] = (fit_id, matchup_id)
            pending.add(fut)
            if len(pending) >= 2 * jobs:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in done:
                    _drain(f)
            if i % PROGRESS_EVERY == 0:
                _log.info("figure progress: %d/%d submitted", i, len(todo))
        for f in wait(pending).done:
            _drain(f)


def report(store, config: PipelineConfig, *, opener=None) -> dict[str, Any]:
    """Stage 7: build the aggregate site and the (stub-published) release.

    ``opener`` (forwarded by :func:`run` like the other stages) lets the report
    add the OC4 band-ratio Chl cross-check, which re-reads each matchup's pixel.
    """
    from pab.report import publish, rst

    site = rst.build_site(store, config.out() / "site", opener=opener)
    release = publish.publish_release(store, config.out() / "release")
    return {
        "site": {k: str(v) for k, v in site.items()},
        "n_uploaded": release["n_uploaded"],
        "manifest": str(release["manifest_path"]),
    }


_STAGE_FUNCS = {
    "ingest": ingest,
    "discover": discover,
    "match": match,
    "fit": fit,
    "figure": figure,
    "report": report,
}


def run(
    store,
    config: PipelineConfig | None = None,
    *,
    stages=STAGES,
    opener=None,
    fetcher=None,
    searcher=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the selected pipeline stages in order; return a per-stage summary.

    Args:
        store: An open :class:`pab.db.store.Store` (the shared state).
        config: The :class:`PipelineConfig` (defaults to the dev-set defaults).
        stages: Which stages to run (subset of :data:`STAGES`, run in
            :data:`STAGES` order).
        opener, fetcher, searcher: Injectable seams for the granule open, argopy
            fetch, and earthaccess discovery (mocked offline; live by default).
        dry_run: If True, return the planned stage order and do nothing.

    Returns:
        ``{"dry_run": True, "stages": [...]}`` on a dry run, else
        ``{stage: <summary>}`` for each executed stage.
    """
    config = config or PipelineConfig()
    plan = [s for s in STAGES if s in set(stages)]
    if dry_run:
        return {"dry_run": True, "stages": plan, "pab_version": _pab_version}

    # Off-cloud pre-download path: read granules from a reliable local cache
    # rather than lazy out-of-region S3/HTTPS (Q&A Task 2). An explicitly injected
    # opener (the test seam) always wins.
    if opener is None and config.download:
        from pab.pace.cloud import cached_opener

        opener = cached_opener(config.cache())

    seam = {"opener": opener, "fetcher": fetcher, "searcher": searcher}
    summary: dict[str, Any] = {}
    for stage in plan:
        func = _STAGE_FUNCS[stage]
        # forward only the seam(s) the stage actually declares as parameters
        # (signature, not co_varnames, so a same-named local can't misroute)
        params = inspect.signature(func).parameters
        kwargs = {k: v for k, v in seam.items() if k in params}
        summary[stage] = func(store, config, **kwargs)
    return summary


# -- CLI --------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """The ``pab`` CLI parser."""
    p = argparse.ArgumentParser(
        prog="pab", description="Run the PAB end-to-end matchup pipeline."
    )
    p.add_argument(
        "--db",
        default=str(Path(DATA_DIR) / "pab.db"),
        help="SQLite store path (created if absent).",
    )
    p.add_argument(
        "--stage",
        action="append",
        choices=STAGES,
        dest="stages",
        help="Run only this stage (repeatable). Default: all.",
    )
    p.add_argument(
        "--outdir", default=None, help="Output dir (default DATA_DIR/pipeline)."
    )
    p.add_argument("--profiles-csv", default=None, help="Profile-selection CSV.")
    p.add_argument("--replace", action="store_true", help="Re-do completed work.")
    p.add_argument("--no-figures", action="store_true", help="Skip the figure stage.")
    p.add_argument(
        "--download",
        action="store_true",
        help="Pre-download granules to a local cache and read them locally "
        "(reliable off-cloud; use this when not running in-region us-west-2).",
    )
    p.add_argument(
        "--cache-dir",
        default=None,
        help="Granule download cache dir (default DATA_DIR/granules).",
    )
    p.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Parallel processes for the match + fit stages (profile/matchup "
        "level; 1 = serial).",
    )
    p.add_argument(
        "--ingest-jobs",
        type=int,
        default=None,
        help="Concurrent argopy fetches in the ingest stage (worker processes). "
        f"Default: --jobs capped at {PipelineConfig.INGEST_JOBS_CAP} (the Argo "
        "servers are shared).",
    )
    p.add_argument(
        "--discover-jobs",
        type=int,
        default=None,
        help="Concurrent CMR searches in the discover stage (threads). Default: "
        f"--jobs capped at {PipelineConfig.DISCOVER_JOBS_CAP} (CMR is shared).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the stage plan and exit without touching anything.",
    )
    p.add_argument(
        "--emit-site",
        default=None,
        metavar="DIR",
        help="Generate the reporting-site sources (rst.build_site) into DIR from "
        "the --db store and exit. Use to (re)generate an in-repo report_site/ for "
        "Read the Docs to build (see HOWTO §7).",
    )
    p.add_argument(
        "--downloads-base-url",
        default=None,
        metavar="URL",
        help="With --emit-site: link the summary tables at this URL prefix (e.g. "
        "the s3://pab public URL) instead of staging multi-MB CSV/Parquet into the "
        "committed site. Keeps report_site/ bounded at scale (HOWTO §7b).",
    )
    return p


def main(argv=None) -> int:
    """CLI entry point (``pab``). Returns a process exit code."""
    from pab.db import Store

    args = build_parser().parse_args(argv)
    # Without a handler the stages' progress/failure logs vanish (only WARNING+
    # reached stderr via logging's last-resort handler during the 1k run).
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = PipelineConfig(
        profiles_csv=args.profiles_csv,
        outdir=args.outdir,
        replace=args.replace,
        make_figures=not args.no_figures,
        download=args.download,
        cache_dir=args.cache_dir,
        jobs=args.jobs,
        ingest_jobs=args.ingest_jobs,
        discover_jobs=args.discover_jobs,
    )
    stages = args.stages or list(STAGES)
    if args.dry_run:
        plan = run(None, config, stages=stages, dry_run=True)
        print("pab pipeline (dry run) — stages:", " → ".join(plan["stages"]))
        print("db:", args.db, "| outdir:", config.out())
        if config.download:
            print("granule access: pre-download → local cache:", config.cache())
        return 0
    if args.emit_site:
        # Standalone: (re)generate the RTD reporting-site sources from the store.
        # With --download, reuse the local granule cache so the OC4 Chl cross-check
        # (chl_oc) can be added without slow/uncertain out-of-region reads.
        from pab.report import rst

        opener = None
        if config.download:
            from pab.pace.cloud import cached_opener

            opener = cached_opener(config.cache())
        with Store.open(Path(args.db)) as store:
            written = rst.build_site(
                store,
                args.emit_site,
                opener=opener,
                downloads_base_url=args.downloads_base_url,
            )
        print(f"emitted reporting site → {args.emit_site}")
        for name, path in sorted(written.items()):
            print(f"  {name}: {path}")
        return 0
    created = datetime.now(UTC).isoformat()
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)  # sqlite won't create the dir
    with Store.open(db) as store:
        summary = run(store, config, stages=stages)
    print(f"pab pipeline done ({created}); stages: {list(summary)}")
    for stage, res in summary.items():
        print(f"  {stage}: {res}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
