"""Stage 8 tests: the end-to-end pipeline & CLI (``pab.pipeline``)."""

import numpy as np
import pytest
import xarray as xr

from pab import pipeline
from pab.db import Store
from pab.fit.models import FitConfig
from pab.pace import cloud, flags


def _granule(center=(20.0, -50.0), span=0.02, nwave=31):
    """A tiny unflagged canonical granule centred on the float (sub-km pixels)."""
    nx = ny = 5
    clat, clon = center
    lat = np.linspace(clat - span, clat + span, nx)
    lon = np.linspace(clon - span, clon + span, ny)
    lons2d, lats2d = np.meshgrid(lon, lat)
    wave = np.linspace(400.0, 700.0, nwave)
    rrs = np.tile(0.01 * np.exp(-(wave - 400.0) / 150.0), (nx, ny, 1))
    return xr.Dataset(
        {
            "Rrs": (("x", "y", "wl"), rrs),
            "Rrs_unc": (("x", "y", "wl"), rrs * 0.05),
            "l2_flags": (("x", "y"), np.zeros((nx, ny), dtype=np.int64)),
        },
        coords={
            "latitude": (("x", "y"), lats2d),
            "longitude": (("x", "y"), lons2d),
            "wavelength": ("wl", wave),
        },
    )


def _profiles():
    """Two inline profiles with precomputed mixed-layer summaries (offline)."""
    return [
        {
            "wmo": 7902226,
            "cycle": 5,
            "latitude": 20.0,
            "longitude": -50.0,
            "time": "2025-02-18T20:00:00",
            "summary": {
                "mld": 30.0,
                "mld_method": "x",
                "bbp700": 1e-3,
                "chla": 0.1,
                "n_points": 6,
            },
        },
        {
            "wmo": 7902136,
            "cycle": 8,
            "latitude": 4.0,
            "longitude": -137.0,
            "time": "2025-01-25T13:00:00",
            "summary": {
                "mld": 30.0,
                "mld_method": "x",
                "bbp700": 2e-3,
                "chla": 0.2,
                "n_points": 6,
            },
        },
    ]


def _gid(lat, lon):
    return f"PACE_{lat:.0f}_{lon:.0f}"


def _searcher(lat, lon, t0, t1, config):
    """Offline discovery seam: one granule at the float, mid-window."""
    import pandas as pd

    mid = t0 + (t1 - t0) / 2
    gid = _gid(lat, lon)
    return pd.DataFrame(
        [
            {
                "id": gid,
                "time": mid.isoformat(),
                "polygon": None,
                "CC": 5.0,
                "url": f"s3://b/{gid}.nc",
            }
        ]
    )


def _opener_for(profiles):
    """A source→granule opener returning a granule centred on each float."""
    grans = {
        f"s3://b/{_gid(p['latitude'], p['longitude'])}.nc": _granule(
            (p["latitude"], p["longitude"])
        )
        for p in profiles
    }
    return lambda src: grans[src]


# -- orchestration (no heavy deps) ------------------------------------------
def test_dry_run_plans_without_touching():
    out = pipeline.run(None, pipeline.PipelineConfig(), dry_run=True)
    assert out["dry_run"] and out["stages"] == list(pipeline.STAGES)


def test_stage_subset_runs_only_requested():
    cfg = pipeline.PipelineConfig(profiles=_profiles())
    with Store.open(":memory:") as store:
        out = pipeline.run(store, cfg, stages=("ingest",))
        assert set(out) == {"ingest"}
        assert store.count("mld_summary") == 2


def test_ingest_is_idempotent():
    cfg = pipeline.PipelineConfig(profiles=_profiles())
    with Store.open(":memory:") as store:
        first = pipeline.run(store, cfg, stages=("ingest",))["ingest"]
        assert len(first["written"]) == 2 and first["skipped"] == []
        second = pipeline.run(store, cfg, stages=("ingest",))["ingest"]
        assert second["written"] == [] and len(second["skipped"]) == 2
        assert store.count("mld_summary") == 2  # no duplicates


def test_ingest_survives_a_bad_profile():
    # one good (offline) profile + one whose live fetch fails: the bad one is
    # recorded under "failed" and does NOT abort the stage (a single 0-d array or
    # fetch error must not kill a 50k-profile ingest — the pilot crash).
    good = _profiles()[0]  # has a precomputed summary (offline path)
    bad = {"wmo": 5905000, "cycle": 1}  # no summary -> live fetch path

    def _boom(*_a, **_k):
        raise RuntimeError("argopy fetch failed")

    with Store.open(":memory:") as store:
        out = pipeline.ingest(
            store, pipeline.PipelineConfig(profiles=[good, bad]), fetcher=_boom
        )
        assert out["written"] == ["7902226_5"]
        assert out["failed"] == ["5905000_1"]
        assert store.count("mld_summary") == 1  # the good profile still persisted


def test_discover_with_searcher_seam_and_resume():
    cfg = pipeline.PipelineConfig(profiles=_profiles())
    with Store.open(":memory:") as store:
        pipeline.run(store, cfg, stages=("ingest",))
        out = pipeline.run(store, cfg, stages=("discover",), searcher=_searcher)
        assert out["discover"]["granules_upserted"] == 2
        assert store.count("granules") == 2

        # resume: both profiles already have in-window granules -> skipped, no re-query
        def _boom(*a, **k):  # would fire if discover re-queried
            raise AssertionError("re-queried an already-discovered profile")

        again = pipeline.run(store, cfg, stages=("discover",), searcher=_boom)
        assert again["discover"]["granules_upserted"] == 0
        assert len(again["discover"]["skipped"]) == 2


def test_match_through_pipeline_and_resume():
    profiles = _profiles()
    cfg = pipeline.PipelineConfig(profiles=profiles)
    opener = _opener_for(profiles)
    with Store.open(":memory:") as store:
        pipeline.run(store, cfg, stages=("ingest", "discover"), searcher=_searcher)
        out = pipeline.run(store, cfg, stages=("match",), opener=opener)
        assert len(out["match"]["written"]) == 2
        assert store.count("matchups") == 2
        # resume: a second match writes nothing new
        again = pipeline.run(store, cfg, stages=("match",), opener=opener)
        assert again["match"]["written"] == [] and len(again["match"]["skipped"]) == 2


def test_config_cache_dir_default_and_override(tmp_path):
    assert pipeline.PipelineConfig().cache().name == "granules"
    assert pipeline.PipelineConfig(cache_dir=tmp_path).cache() == tmp_path


def test_run_builds_cached_opener_when_download_set(monkeypatch, tmp_path):
    # download=True (and no injected opener) -> run() routes stages through the
    # local-cache opener built from config.cache().
    profiles = _profiles()
    built = {}

    def _fake_cached_opener(cache_dir):
        built["cache_dir"] = cache_dir
        return _opener_for(profiles)

    monkeypatch.setattr(cloud, "cached_opener", _fake_cached_opener)
    cfg = pipeline.PipelineConfig(
        profiles=profiles, download=True, cache_dir=tmp_path
    )
    with Store.open(":memory:") as store:
        pipeline.run(store, cfg, stages=("ingest", "discover"), searcher=_searcher)
        out = pipeline.run(store, cfg, stages=("match",))
        assert len(out["match"]["written"]) == 2
        assert built["cache_dir"] == tmp_path


def test_report_stage_on_empty_store(tmp_path):
    cfg = pipeline.PipelineConfig(outdir=tmp_path)
    with Store.open(":memory:") as store:
        out = pipeline.run(store, cfg, stages=("report",))
        assert (tmp_path / "site" / "summary.rst").exists()
        assert (tmp_path / "release" / "manifest.json").exists()
        assert out["report"]["n_uploaded"] == 0  # no artifacts yet


# -- CLI --------------------------------------------------------------------
def test_cli_dry_run(capsys, tmp_path):
    rc = pipeline.main(["--dry-run", "--db", str(tmp_path / "pab.db")])
    assert rc == 0
    assert "dry run" in capsys.readouterr().out


def test_cli_parser_stage_subset():
    args = pipeline.build_parser().parse_args(["--stage", "match", "--stage", "fit"])
    assert args.stages == ["match", "fit"]


def test_cli_parser_jobs():
    assert pipeline.build_parser().parse_args([]).jobs == 1  # serial default
    assert pipeline.build_parser().parse_args(["--jobs", "8"]).jobs == 8


def test_emit_profile_qa_writes_and_records(tmp_path):
    # the Q&A figure is rendered to outdir/argo_qa and its path recorded in the DB
    import numpy as np

    from pab.argo.summary import persist_summary

    with Store.open(":memory:") as store:
        pid = persist_summary(
            store,
            wmo=1,
            cycle=2,
            summary={
                "mld": 30.0,
                "mld_method": "x",
                "bbp700": 1e-3,
                "chla": 0.1,
                "n_points": 5,
            },
            latitude=0.0,
            longitude=0.0,
            time="2025-01-01T00:00:00",
        )
        cfg = pipeline.PipelineConfig(outdir=tmp_path)
        pipeline._emit_profile_qa(
            store,
            pid,
            1,
            2,
            cfg,
            pres=np.linspace(0, 100, 20),
            bbp700=np.linspace(2e-3, 1e-3, 20),
            chla=np.linspace(0.2, 0.1, 20),
            mld=30.0,
        )
        png = tmp_path / "argo_qa" / "1_2.png"
        assert png.exists()
        row = store.query(
            "SELECT qa_path FROM mld_summary WHERE profile_id = ?", (pid,)
        )[0]
        assert row["qa_path"] == str(png)


def test_emit_profile_qa_respects_no_figures(tmp_path):
    import numpy as np

    from pab.argo.summary import persist_summary

    with Store.open(":memory:") as store:
        pid = persist_summary(
            store,
            wmo=1,
            cycle=2,
            summary={"mld": 30.0, "mld_method": "x", "bbp700": 1e-3, "n_points": 5},
            latitude=0.0,
            longitude=0.0,
            time="2025-01-01T00:00:00",
        )
        cfg = pipeline.PipelineConfig(outdir=tmp_path, make_figures=False)
        pipeline._emit_profile_qa(
            store, pid, 1, 2, cfg, pres=np.linspace(0, 100, 20),
            bbp700=np.linspace(2e-3, 1e-3, 20), chla=None, mld=30.0,
        )
        assert not (tmp_path / "argo_qa").exists()


def test_figure_stage_backfills_existing_scene(tmp_path):
    # a plain `figure` run (no --replace) records an already-on-disk scene PNG
    # into matchups.scene_path, without re-rendering (no bing needed).
    from pab.argo.summary import persist_summary

    with Store.open(":memory:") as store:
        pid = persist_summary(
            store,
            wmo=1,
            cycle=2,
            summary={"mld": 30.0, "mld_method": "x", "bbp700": 1e-3, "n_points": 5},
            latitude=0.0,
            longitude=0.0,
            time="2025-01-01T00:00:00",
        )
        store.upsert("granules", {"granule_id": "G1", "data_url": "s3://b/G1.nc"})
        store.upsert(
            "matchups",
            {"matchup_id": "M1", "profile_id": pid, "granule_id": "G1", "n_spectra": 1},
        )
        store.upsert(
            "fits",
            {
                "fit_id": "M1_ExpBPow",
                "matchup_id": "M1",
                "algorithm": "BING",
                "model_pair": "ExpBPow",
                "figure_path": "/already/rendered_fit.png",  # so the fit is skipped
                "pab_version": "0",
            },
        )
        figdir = tmp_path / "figures"
        figdir.mkdir(parents=True)
        (figdir / "M1_scene.png").write_bytes(b"fake-scene")
        out = pipeline.figure(store, pipeline.PipelineConfig(outdir=tmp_path))
        assert "M1_ExpBPow" in out["skipped"]  # re-render skipped, but…
        row = store.query("SELECT scene_path FROM matchups WHERE matchup_id = 'M1'")[0]
        assert row["scene_path"] == str(figdir / "M1_scene.png")  # …scene backfilled


def test_cli_emit_site(capsys, tmp_path):
    # --emit-site generates the RTD reporting-site sources from the DB and exits
    # (no pipeline stages run); used to (re)generate an in-repo report_site/.
    db = tmp_path / "pab.db"
    with Store.open(db) as store:
        pass  # an empty store is enough for the smoke (build_site handles len==0)
    out = tmp_path / "report_site"
    rc = pipeline.main(["--db", str(db), "--emit-site", str(out)])
    assert rc == 0
    assert (out / "summary.rst").exists() and (out / "conf.py").exists()
    assert "emitted reporting site" in capsys.readouterr().out


def test_cli_creates_db_parent_dir(tmp_path):
    # a --db path under a not-yet-existing dir must work (sqlite won't mkdir it)
    db = tmp_path / "new" / "sub" / "pab.db"
    rc = pipeline.main(
        ["--db", str(db), "--stage", "report", "--outdir", str(tmp_path / "out")]
    )
    assert rc == 0 and db.exists()


# -- end-to-end (needs bing + emcee) ----------------------------------------
def test_end_to_end_offline():
    pytest.importorskip("bing")
    pytest.importorskip("emcee")
    import os
    import tempfile

    profiles = _profiles()
    cfg = pipeline.PipelineConfig(
        profiles=profiles,
        fit=FitConfig(nsteps=400, nburn=100, analysis_burn=100),
        outdir=tempfile.mkdtemp(),
        make_figures=False,  # the figure stage's reconstruct needs the Loisel data
    )
    with Store.open(":memory:") as store:
        summary = pipeline.run(
            store,
            cfg,
            stages=pipeline.STAGES,
            opener=_opener_for(profiles),
            searcher=_searcher,
        )
        assert set(summary) >= {"ingest", "discover", "match", "fit", "report"}
        assert store.count("matchups") == 2  # the chain reached Stage 4
        # the report site was generated regardless of fit success
        assert os.path.exists(cfg.out() / "site" / "summary.rst")
        # if the fits ran (BING data present), results were persisted
        if summary["fit"]["written"]:
            assert store.count("fit_results") > 0


def test_discover_searches_a_distant_profile_in_the_same_time_window():
    """Granules over one ocean must not suppress the search for another ocean.

    The skip test used to be time-only, so once *any* granule sat within +-24 h
    of a profile's time that profile was skipped — at 1000 profiles ~71 % were
    starved of granules (they could then never match). Skipping must be keyed on
    coverage of the profile's own position.
    """
    import pandas as pd

    calls = []

    def searcher(lat, lon, t0, t1, config):
        calls.append((round(lat, 1), round(lon, 1)))
        mid = t0 + (t1 - t0) / 2
        # a 10-deg box footprint around the float, as CMR reports
        poly = (
            f"POLYGON (({lon - 5:.2f} {lat - 5:.2f}, {lon + 5:.2f} {lat - 5:.2f}, "
            f"{lon + 5:.2f} {lat + 5:.2f}, {lon - 5:.2f} {lat + 5:.2f}, "
            f"{lon - 5:.2f} {lat - 5:.2f}))"
        )
        return pd.DataFrame(
            [
                {
                    "id": f"G_{lat:.0f}_{lon:.0f}",
                    "time": mid.isoformat(),
                    "polygon": poly,
                    "CC": 5.0,
                    "url": f"s3://b/G_{lat:.0f}_{lon:.0f}.nc",
                }
            ]
        )

    summary = {"mld": 30.0, "mld_method": "x", "n_points": 5}
    profiles = [  # N Pacific, then N Atlantic 8 h later, then S Indian +22 h
        {"wmo": 1111, "cycle": 1, "latitude": 30.0, "longitude": -140.0,
         "time": "2024-06-01T02:00:00", "summary": summary},
        {"wmo": 2222, "cycle": 1, "latitude": 35.0, "longitude": -40.0,
         "time": "2024-06-01T10:00:00", "summary": summary},
        {"wmo": 3333, "cycle": 1, "latitude": -45.0, "longitude": 20.0,
         "time": "2024-06-02T00:00:00", "summary": summary},
    ]
    cfg = pipeline.PipelineConfig(profiles=profiles)
    with Store.open(":memory:") as store:
        pipeline.run(store, cfg, stages=("ingest",))
        out = pipeline.run(store, cfg, stages=("discover",), searcher=searcher)
        assert out["discover"]["skipped"] == []
        assert len(calls) == 3  # every profile got its own search
        assert store.count("granules") == 3

        # resume: each profile now has a granule over its own position -> skipped
        again = pipeline.run(store, cfg, stages=("discover",), searcher=searcher)
        assert len(again["discover"]["skipped"]) == 3
        assert len(calls) == 3  # no re-query


# -- parallel ingest --------------------------------------------------------
def _live_profiles(n):
    """n profiles with no precomputed summary -> they take the live-fetch path."""
    return [
        {
            "wmo": 7900000 + i,
            "cycle": 1,
            "latitude": 10.0 + i,
            "longitude": -40.0 - i,
            "time": "2025-05-01T12:00:00",
        }
        for i in range(n)
    ]


def _dataset_fetcher(record=None, fail_on=()):
    """A fetcher seam standing in for argopy.

    argopy is not a test dependency (``iter_profiles`` needs its ``.argo``
    accessor), so the fetcher returns a marker dict and ``_stub_iter_profiles``
    below turns it into the ``(meta, variables)`` pair the stage consumes.
    """

    def fetcher(wmo, cycle, src, mode):
        if record is not None:
            record.append(wmo)
        if wmo in fail_on:
            raise RuntimeError("argopy fetch failed")
        return {"wmo": wmo, "cycle": cycle}

    return fetcher


def _stub_iter_profiles(ds):
    import numpy as np

    meta = {
        "wmo": ds["wmo"],
        "cycle": ds["cycle"],
        "latitude": 10.0,
        "longitude": -40.0,
        "time": "2025-05-01T12:00:00",
    }
    variables = {
        "PRES": np.linspace(0.0, 100.0, 12),
        "BBP700": np.full(12, 2e-3),
        "CHLA": np.full(12, 0.2),
        "TEMP": np.linspace(20.0, 10.0, 12),
        "PSAL": np.full(12, 35.0),
    }
    yield meta, variables


@pytest.fixture
def stub_iter_profiles(monkeypatch):
    # the live-fetch path summarizes a real profile -> needs gsw for sigma0
    pytest.importorskip("gsw")
    from pab.argo import fetch as argo_fetch

    monkeypatch.setattr(argo_fetch, "iter_profiles", _stub_iter_profiles)


def test_ingest_parallel_matches_serial(stub_iter_profiles):
    """The thread pool must persist exactly what the serial path does."""
    profiles = _live_profiles(6)
    cfg_par = pipeline.PipelineConfig(profiles=profiles, ingest_jobs=4, make_figures=False)
    cfg_ser = pipeline.PipelineConfig(profiles=profiles, make_figures=False)

    with Store.open(":memory:") as store:
        out = pipeline.ingest(store, cfg_par, fetcher=_dataset_fetcher())
        rows = store.query(
            "SELECT p.wmo, m.mld, m.bbp700 FROM mld_summary m "
            "JOIN profiles p ON p.profile_id = m.profile_id ORDER BY p.wmo"
        )
    with Store.open(":memory:") as store:
        ser = pipeline.ingest(store, cfg_ser, fetcher=_dataset_fetcher())
        rows_ser = store.query(
            "SELECT p.wmo, m.mld, m.bbp700 FROM mld_summary m "
            "JOIN profiles p ON p.profile_id = m.profile_id ORDER BY p.wmo"
        )

    assert set(out["written"]) == set(ser["written"]) and len(out["written"]) == 6
    assert out["failed"] == [] and rows == rows_ser


def test_ingest_parallel_is_resumable_and_survives_failures(stub_iter_profiles):
    profiles = _live_profiles(5)
    cfg = pipeline.PipelineConfig(profiles=profiles, ingest_jobs=3, make_figures=False)
    bad = profiles[2]["wmo"]
    with Store.open(":memory:") as store:
        out = pipeline.ingest(store, cfg, fetcher=_dataset_fetcher(fail_on=(bad,)))
        assert out["failed"] == [f"{bad}_1"]
        assert len(out["written"]) == 4
        assert store.count("mld_summary") == 4

        # resume: the four good ones are skipped, only the failure is retried
        tried = []
        again = pipeline.ingest(store, cfg, fetcher=_dataset_fetcher(record=tried))
        assert len(again["skipped"]) == 4
        assert tried == [bad]  # no re-fetch of the profiles already stored
        assert again["written"] == [f"{bad}_1"]
        assert store.count("mld_summary") == 5


def test_ingest_workers_caps_derived_concurrency():
    # --jobs is sized for the CPU-bound stages; ingest must not open 50 fetches
    assert pipeline.PipelineConfig(jobs=50).ingest_workers() == 16
    assert pipeline.PipelineConfig(jobs=4).ingest_workers() == 4
    assert pipeline.PipelineConfig(jobs=50, ingest_jobs=24).ingest_workers() == 24
    assert pipeline.PipelineConfig().ingest_workers() == 1


def test_cli_parser_ingest_jobs():
    args = pipeline.build_parser().parse_args(["--jobs", "50", "--ingest-jobs", "8"])
    assert (args.jobs, args.ingest_jobs) == (50, 8)
    assert pipeline.build_parser().parse_args([]).ingest_jobs is None


def _module_level_fetcher(wmo, cycle, src, mode):  # picklable -> process pool
    return {"wmo": wmo, "cycle": cycle}


def test_ingest_executor_prefers_processes_when_picklable():
    """The live fetch is GIL-bound, not network-bound (measured: 12 threads
    2.75 s/profile vs 12 processes 0.97), so the pool must be processes whenever
    the fetcher can cross a spawn boundary — and threads when it cannot."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    ex, kind = pipeline._ingest_executor(None, 2)  # live fetch
    with ex:
        assert kind == "processes" and isinstance(ex, ProcessPoolExecutor)
    ex, kind = pipeline._ingest_executor(_module_level_fetcher, 2)
    with ex:
        assert kind == "processes"
    ex, kind = pipeline._ingest_executor(lambda *a: None, 2)  # closure seam
    with ex:
        assert kind == "threads" and isinstance(ex, ThreadPoolExecutor)


# -- discover robustness (the 1k-run abort) ---------------------------------
def test_search_bbox_is_clamped_to_cmr_limits():
    """CMR rejects a box outside [-180,180]x[-90,90].

    A float at lon -179.86 with the default 0.4 deg pad produced
    west = -180.2566, and CMR's 400 aborted the whole discover stage 23 profiles
    into the 1000-profile run.
    """
    w, s, e, n = pipeline.search_bbox(-179.8566, -45.0, 0.4)
    assert w == -180.0 and e == pytest.approx(-179.4566)
    w, s, e, n = pipeline.search_bbox(179.9, 89.8, 0.4)
    assert e == 180.0 and n == 90.0
    # the box must still contain the float, or the search is meaningless
    for lon, lat in ((-179.99, 0.0), (179.99, 0.0), (0.0, 89.99), (0.0, -89.99)):
        w, s, e, n = pipeline.search_bbox(lon, lat, 0.4)
        assert w <= lon <= e and s <= lat <= n
        assert -180.0 <= w and e <= 180.0 and -90.0 <= s and n <= 90.0


def test_discover_survives_a_failing_search():
    """One bad CMR query must not abort the stage (it truncated the 1k run)."""
    summary = {"mld": 30.0, "mld_method": "x", "n_points": 5}
    profiles = [
        {"wmo": 1111, "cycle": 1, "latitude": 30.0, "longitude": -140.0,
         "time": "2024-06-01T02:00:00", "summary": summary},
        {"wmo": 2222, "cycle": 1, "latitude": -45.0, "longitude": 20.0,
         "time": "2024-09-01T10:00:00", "summary": summary},
    ]

    def searcher(lat, lon, t0, t1, config):
        if lat == 30.0:
            raise RuntimeError('{"errors":["West must be within [-180.0]..."]}')
        return _searcher(lat, lon, t0, t1, config)

    cfg = pipeline.PipelineConfig(profiles=profiles)
    with Store.open(":memory:") as store:
        pipeline.run(store, cfg, stages=("ingest",))
        out = pipeline.discover(store, cfg, searcher=searcher)
        assert out["failed"] == ["1111_1"]          # recorded, not raised
        assert out["granules_upserted"] == 1        # the good profile still ran
        assert store.count("granules") == 1


def test_search_with_retry_recovers_from_a_transient_failure(monkeypatch):
    """CMR 5xx are routine at scale (~1.7% of the 54k discover-count)."""
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda *_: None)  # no real backoff in tests
    calls = []

    def flaky(lat, lon, t0, t1, config):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("CMR 500")
        return "table"

    assert pipeline._search_with_retry(flaky, 0.0, 0.0, None, None, None) == "table"
    assert len(calls) == 3

    def always_bad(lat, lon, t0, t1, config):
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError, match="permanent"):
        pipeline._search_with_retry(always_bad, 0.0, 0.0, None, None, None)


# -- parallel figure stage --------------------------------------------------
def _stub_render(db_path, fit_id, matchup_id, figdir, opener, *, store=None):
    """Module-level stand-in for _render_figure: writes the files, no plotting.

    Keeps the test about the fan-out + parent-side bookkeeping (the renderers
    themselves need BING/Loisel data, which CI does not have).
    """
    from pathlib import Path

    figdir = Path(figdir)
    if fit_id.endswith("_bad"):
        raise RuntimeError("render failed")
    fpath = figdir / f"{fit_id}_fit.png"
    fpath.write_bytes(b"png")
    spath = figdir / f"{matchup_id}_scene.png"
    spath.write_bytes(b"png")
    return str(fpath), str(spath)


def _seed_fits(store, n):
    """n matchups each with a fit row, enough for the figure stage to iterate."""
    from pab.argo.summary import persist_summary

    ids = []
    for i in range(n):
        wmo = 7900100 + i
        pid = persist_summary(
            store,
            wmo=wmo,
            cycle=1,
            summary={"mld": 30.0, "mld_method": "x", "n_points": 5},
            latitude=10.0 + i,
            longitude=-40.0,
            time="2025-05-01T12:00:00",
        )
        gid = f"G{i}"
        store.upsert("granules", {"granule_id": gid, "time_start": "2025-05-01T11:30:00"})
        mid = f"{wmo}_1_{gid}"
        store.upsert(
            "matchups",
            {"matchup_id": mid, "profile_id": pid, "granule_id": gid, "n_spectra": 1},
        )
        fid = f"fit{i}_bad" if i == 0 else f"fit{i}"
        store.upsert(
            "fits",
            {
                "fit_id": fid,
                "matchup_id": mid,
                "model_pair": "ExpBPow",
                "pab_version": "test",
            },
        )
        ids.append((fid, mid))
    return ids


def test_figure_parallel_records_paths_and_contains_failures(tmp_path, monkeypatch):
    """The parallel figure path must write exactly what the serial one records.

    figure is the most expensive stage per matchup (42 s measured in-pod), so it
    fans out like match/fit — workers render, the parent writes the paths.
    """
    monkeypatch.setattr(pipeline, "_render_figure", _stub_render)
    db = tmp_path / "fig.db"
    cfg = pipeline.PipelineConfig(outdir=tmp_path / "out", jobs=3)
    with Store.open(db) as store:
        _seed_fits(store, 5)
        out = pipeline.figure(store, cfg)
        assert sorted(out["written"]) == ["fit1", "fit2", "fit3", "fit4"]
        assert out["failed"] == ["fit0_bad"]  # contained, not raised
        rows = store.query(
            "SELECT fit_id, figure_path FROM fits WHERE figure_path IS NOT NULL"
        )
        assert len(rows) == 4
        assert store.count("matchups") == 5
        scenes = store.query("SELECT scene_path FROM matchups WHERE scene_path IS NOT NULL")
        assert len(scenes) == 4

        # resume: everything with a figure_path is skipped, nothing re-rendered
        again = pipeline.figure(store, cfg)
        assert sorted(again["skipped"]) == ["fit1", "fit2", "fit3", "fit4"]
        assert again["written"] == [] and again["failed"] == ["fit0_bad"]


def test_figure_serial_when_db_is_in_memory(tmp_path, monkeypatch):
    """A :memory: store cannot be shared with workers -> render serially."""
    monkeypatch.setattr(pipeline, "_render_figure", _stub_render)
    cfg = pipeline.PipelineConfig(outdir=tmp_path / "out", jobs=4)
    with Store.open(":memory:") as store:
        assert pipeline._store_path(store) is None
        _seed_fits(store, 3)
        out = pipeline.figure(store, cfg)
        assert sorted(out["written"]) == ["fit1", "fit2"]
        assert out["failed"] == ["fit0_bad"]


def test_store_path_reports_the_file(tmp_path):
    db = tmp_path / "p.db"
    with Store.open(db) as store:
        assert pipeline._store_path(store) == str(db)


def test_discover_concurrent_matches_serial(monkeypatch):
    """Threaded discover must persist exactly what the serial path does.

    CMR queries are pure latency: 1.75 s each serially is 26 h over the full
    selection, versus ~2 h at 8 threads (measured by the one-off count script).
    """
    summary = {"mld": 30.0, "mld_method": "x", "n_points": 5}
    profiles = [
        {
            "wmo": 5900000 + i,
            "cycle": 1,
            "latitude": -60.0 + 12.0 * i,      # far apart, so none covers another
            "longitude": -150.0 + 40.0 * i,
            "time": f"2024-0{1 + i}-15T12:00:00",
            "summary": summary,
        }
        for i in range(6)
    ]

    def run(jobs):
        calls = []

        def searcher(lat, lon, t0, t1, config):
            calls.append((round(lat, 1), round(lon, 1)))
            return _searcher(lat, lon, t0, t1, config)

        cfg = pipeline.PipelineConfig(profiles=profiles, discover_jobs=jobs)
        with Store.open(":memory:") as store:
            pipeline.run(store, cfg, stages=("ingest",))
            out = pipeline.discover(store, cfg, searcher=searcher)
            rows = sorted(r["granule_id"] for r in store.query("SELECT granule_id FROM granules"))
        return out, rows, sorted(calls)

    par, par_rows, par_calls = run(4)
    ser, ser_rows, ser_calls = run(1)
    assert par["granules_upserted"] == ser["granules_upserted"] == 6
    assert par_rows == ser_rows
    assert par_calls == ser_calls          # every profile searched exactly once
    assert par["failed"] == [] and par["skipped"] == []


def test_discover_concurrent_contains_a_failing_search():
    summary = {"mld": 30.0, "mld_method": "x", "n_points": 5}
    profiles = [
        {"wmo": 5910000 + i, "cycle": 1, "latitude": -50.0 + 25.0 * i,
         "longitude": -120.0 + 60.0 * i, "time": f"2024-0{1 + i}-10T12:00:00",
         "summary": summary}
        for i in range(4)
    ]

    def searcher(lat, lon, t0, t1, config):
        if round(lat) == -25:
            raise RuntimeError("CMR exploded")
        return _searcher(lat, lon, t0, t1, config)

    cfg = pipeline.PipelineConfig(profiles=profiles, discover_jobs=3)
    with Store.open(":memory:") as store:
        pipeline.run(store, cfg, stages=("ingest",))
        import time as _time

        orig = _time.sleep
        _time.sleep = lambda *_: None  # skip retry backoff
        try:
            out = pipeline.discover(store, cfg, searcher=searcher)
        finally:
            _time.sleep = orig
        assert len(out["failed"]) == 1
        assert out["granules_upserted"] == 3       # the others still landed
        assert store.count("granules") == 3


def test_discover_workers_caps_derived_concurrency():
    assert pipeline.PipelineConfig(jobs=50).discover_workers() == 8
    assert pipeline.PipelineConfig(jobs=4).discover_workers() == 4
    assert pipeline.PipelineConfig(jobs=50, discover_jobs=16).discover_workers() == 16
    assert pipeline.PipelineConfig().discover_workers() == 1


def test_cli_parser_discover_jobs():
    args = pipeline.build_parser().parse_args(["--discover-jobs", "8"])
    assert args.discover_jobs == 8
    assert pipeline.build_parser().parse_args([]).discover_jobs is None


# -- discover honours an explicit selection ---------------------------------
def test_discover_restricts_to_an_explicit_selection():
    """A subset CSV/list must limit discover to those profiles.

    Without this the stage always swept the whole store, so re-searching the
    10,101 profiles the coverage test skipped in the full run would have meant
    re-doing all 53,618 (~8 h instead of ~2 h).
    """
    summary = {"mld": 30.0, "mld_method": "x", "n_points": 5}
    everyone = [
        {"wmo": 5920000 + i, "cycle": 1, "latitude": -60.0 + 24.0 * i,
         "longitude": -160.0 + 55.0 * i, "time": f"2024-0{1 + i}-12T12:00:00",
         "summary": summary}
        for i in range(5)
    ]
    subset = [everyone[1], everyone[3]]

    with Store.open(":memory:") as store:
        pipeline.run(store, pipeline.PipelineConfig(profiles=everyone), stages=("ingest",))
        assert store.count("profiles") == 5

        calls = []

        def searcher(lat, lon, t0, t1, config):
            calls.append(round(lat, 1))
            return _searcher(lat, lon, t0, t1, config)

        out = pipeline.discover(
            store, pipeline.PipelineConfig(profiles=subset), searcher=searcher
        )
        assert sorted(calls) == sorted(round(p["latitude"], 1) for p in subset)
        assert out["granules_upserted"] == 2


def test_discover_without_a_selection_covers_the_whole_store():
    """A bare `--stage discover` must not narrow to the default dev CSV."""
    summary = {"mld": 30.0, "mld_method": "x", "n_points": 5}
    everyone = [
        {"wmo": 5930000 + i, "cycle": 1, "latitude": -40.0 + 30.0 * i,
         "longitude": -150.0 + 70.0 * i, "time": f"2024-0{1 + i}-08T12:00:00",
         "summary": summary}
        for i in range(3)
    ]
    with Store.open(":memory:") as store:
        pipeline.run(store, pipeline.PipelineConfig(profiles=everyone), stages=("ingest",))
        calls = []

        def searcher(lat, lon, t0, t1, config):
            calls.append(round(lat, 1))
            return _searcher(lat, lon, t0, t1, config)

        cfg = pipeline.PipelineConfig()          # no profiles, no CSV
        assert cfg.selection_keys() is None
        out = pipeline.discover(store, cfg, searcher=searcher)
        assert len(calls) == 3                    # every stored profile searched
        assert out["granules_upserted"] == 3


def test_selection_keys_reports_explicit_selection_only(tmp_path):
    assert pipeline.PipelineConfig().selection_keys() is None
    csv = tmp_path / "sel.csv"
    csv.write_text("wmo,cycle,date,latitude,longitude\n7902226,5,2025-02-18T20:00:00Z,20.0,-50.0\n")
    assert pipeline.PipelineConfig(profiles_csv=csv).selection_keys() == {(7902226, 5)}
    assert pipeline.PipelineConfig(profiles=_profiles()).selection_keys() == {
        (7902226, 5), (7902136, 8)
    }
