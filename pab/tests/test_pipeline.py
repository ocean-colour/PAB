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
