"""Stage 10b tests: the NASA-GIOP comparison-baseline ingest (``pab.fit.nasa_giop``).

See ``claude_prompts/pace_giop_gsm.md`` for the design/decision record (Q1-Q6).
"""

import numpy as np
import pytest

from pab.argo.summary import persist_summary
from pab.db import Store
from pab.fit import artifacts, nasa_giop, run
from pab.fit.models import FitConfig
from pab.tests.test_fit import _fake_result
from pab.tests.test_pace import make_iop_granule


def _seed_matchup_with_bing_fit(store, *, aop_url="https://x/G1.L2.OC_AOP.V3_2.nc"):
    """floats->profiles->mld_summary->granule->matchup->pixel->BING fit.

    Returns ``matchup_id``. Mirrors ``pab.tests.test_fit._seed_matchup`` but
    also persists a completed BING fit (a prerequisite for
    :func:`pab.fit.nasa_giop.build_nasa_giop`'s join) and gives the granule a
    real AOP-shaped URL so :func:`pab.pace.iop.iop_source_for_aop` succeeds.
    """
    pid = persist_summary(
        store,
        wmo=7902226,
        cycle=5,
        summary={"mld": 30.0, "mld_method": "x", "chla": 0.12, "n_points": 6},
        latitude=20.0,
        longitude=-50.0,
        time="2025-05-01T12:00:00",
    )
    store.upsert("granules", {"granule_id": "G1", "data_url": aop_url})
    matchup_id = "7902226_5_G1"
    store.upsert(
        "matchups",
        {
            "matchup_id": matchup_id,
            "profile_id": pid,
            "granule_id": "G1",
            "distance_km": 0.0,
            "dtime_hours": 0.5,
            "n_spectra": 1,
        },
    )
    store.upsert(
        "matchup_pixels",
        {
            "matchup_id": matchup_id,
            "ix": 2,
            "iy": 2,
            "latitude": 20.0,
            "longitude": -50.0,
            "rank": 1,
            "flagged": 0,
        },
    )
    pixel_id = store.query(
        "SELECT pixel_id FROM matchup_pixels WHERE matchup_id = ?", (matchup_id,)
    )[0]["pixel_id"]
    artifacts.persist_fit(
        store,
        fit_id=run.make_fit_id(matchup_id, 2, 2, "ExpBPow"),
        matchup_id=matchup_id,
        pixel_id=pixel_id,
        result=_fake_result(),
        config=FitConfig(),
        chains_path="/tmp/F1.npz",
    )
    return matchup_id


# -- pure helpers -------------------------------------------------------------
def test_make_nasa_giop_fit_id():
    assert nasa_giop.make_nasa_giop_fit_id("7902226_5_G1", 1, 1) == (
        "7902226_5_G1_1_1_NASA_GIOP"
    )


# -- persistence ---------------------------------------------------------------
def test_persist_nasa_giop_writes_parallel_fit_row_and_is_idempotent():
    with Store.open(":memory:") as store:
        matchup_id = _seed_matchup_with_bing_fit(store)
        bing_fit_id = run.make_fit_id(matchup_id, 2, 2, "ExpBPow")
        # simulate a BING fit stamped under an *older* production version, to
        # prove the new NASA-GIOP fit row's pab_version doesn't leak onto it
        # (the exact bug the parallel-fits-row design avoids -- Q6).
        store.execute(
            "UPDATE fits SET pab_version = '1.0' WHERE fit_id = ?", (bing_fit_id,)
        )
        quantities = [
            {
                "quantity": "bbp_442",
                "value": 0.004,
                "value_lo": 0.0035,
                "value_hi": 0.0045,
                "unit": "m^-1",
            },
            {
                "quantity": "adg_442",
                "value": 0.03,
                "value_lo": None,
                "value_hi": None,
                "unit": "m^-1",
            },
        ]
        fit_id = nasa_giop.persist_nasa_giop(
            store,
            matchup_id=matchup_id,
            pixel_id=1,
            ix=1,
            iy=1,
            quantities=quantities,
            pab_version="1.1",
        )
        assert fit_id == f"{matchup_id}_1_1_NASA_GIOP"

        fit = store.query("SELECT * FROM fits WHERE fit_id = ?", (fit_id,))[0]
        assert fit["algorithm"] == "NASA_GIOP"
        assert fit["model_pair"] is None
        assert fit["pab_version"] == "1.1"
        # the BING fit is untouched -- still stamped at its own pab_version
        bing_fit = store.query("SELECT * FROM fits WHERE fit_id = ?", (bing_fit_id,))[0]
        assert bing_fit["algorithm"] == "BING"
        assert bing_fit["pab_version"] == "1.0"

        qs = {
            q["quantity"]: q
            for q in store.query(
                "SELECT quantity, value, value_lo, value_hi FROM fit_results WHERE fit_id = ?",
                (fit_id,),
            )
        }
        assert set(qs) == {"NASA_GIOP_bbp_442", "NASA_GIOP_adg_442"}
        assert qs["NASA_GIOP_bbp_442"]["value"] == pytest.approx(0.004)

        # idempotent re-run: one fits row, quantities replaced not duplicated
        nasa_giop.persist_nasa_giop(
            store,
            matchup_id=matchup_id,
            pixel_id=1,
            ix=1,
            iy=1,
            quantities=quantities,
            pab_version="1.1",
        )
        assert store.count("fits") == 2  # BING + NASA_GIOP, no duplicate
        assert (
            len(store.query("SELECT * FROM fit_results WHERE fit_id = ?", (fit_id,)))
            == 2
        )


# -- end-to-end ingest (granule access mocked) ---------------------------------
def test_ingest_nasa_giop_matchup(monkeypatch, tmp_path):
    ds = make_iop_granule()
    # the matchup pixel is at (20.0, -50.0); point the synthetic granule's
    # center pixel (1, 1) there so nearest_pixel locks onto it.
    ds = ds.assign_coords(
        latitude=(("x", "y"), np.full((3, 3), 20.0)),
        longitude=(("x", "y"), np.full((3, 3), -50.0)),
    )

    def fake_download(source, cache_dir, *, replace=False):
        assert "L2.OC_IOP." in str(source)
        return tmp_path / "fake_iop.nc"

    monkeypatch.setattr("pab.pace.cloud.download_granule", fake_download)
    monkeypatch.setattr(nasa_giop._iop, "open_iop_local", lambda fn: ds)

    with Store.open(":memory:") as store:
        matchup_id = _seed_matchup_with_bing_fit(store)
        fit_id = nasa_giop.ingest_nasa_giop_matchup(
            store, matchup_id, cache_dir=tmp_path, pab_version="1.1"
        )
        fit = store.query("SELECT * FROM fits WHERE fit_id = ?", (fit_id,))[0]
        assert fit["algorithm"] == "NASA_GIOP" and fit["pab_version"] == "1.1"
        qs = {
            q["quantity"]: q["value"]
            for q in store.query(
                "SELECT quantity, value FROM fit_results WHERE fit_id = ?", (fit_id,)
            )
        }
        assert qs["NASA_GIOP_bbp_442"] == pytest.approx(0.004)


# -- batch driver ---------------------------------------------------------------
def test_build_nasa_giop_records_failed_without_aborting():
    with Store.open(":memory:") as store:
        # a granule URL with no "L2.OC_AOP." tag -> iop_source_for_aop raises
        matchup_id = _seed_matchup_with_bing_fit(store, aop_url="https://x/weird.nc")
        out = nasa_giop.build_nasa_giop(store, cache_dir="/tmp", pab_version="1.1")
        assert out["written"] == [] and out["skipped"] == []
        assert out["failed"] == [matchup_id]
        assert store.count("fits") == 1  # only the pre-seeded BING fit


def test_build_nasa_giop_skips_already_ingested_matchups(monkeypatch, tmp_path):
    ds = make_iop_granule()
    ds = ds.assign_coords(
        latitude=(("x", "y"), np.full((3, 3), 20.0)),
        longitude=(("x", "y"), np.full((3, 3), -50.0)),
    )
    monkeypatch.setattr(
        "pab.pace.cloud.download_granule",
        lambda source, cache_dir, replace=False: tmp_path / "fake_iop.nc",
    )
    monkeypatch.setattr(nasa_giop._iop, "open_iop_local", lambda fn: ds)

    with Store.open(":memory:") as store:
        matchup_id = _seed_matchup_with_bing_fit(store)
        first = nasa_giop.build_nasa_giop(store, cache_dir=tmp_path, pab_version="1.1")
        assert len(first["written"]) == 1 and first["skipped"] == []

        second = nasa_giop.build_nasa_giop(store, cache_dir=tmp_path, pab_version="1.1")
        assert second["written"] == [] and second["skipped"] == [matchup_id]
        assert store.count("fits") == 2  # BING + one NASA_GIOP, no duplicate


# -- CLI driver (python -m pab.fit.nasa_giop) ------------------------------------
def test_main_runs_and_resumes(monkeypatch, tmp_path):
    ds = make_iop_granule()
    ds = ds.assign_coords(
        latitude=(("x", "y"), np.full((3, 3), 20.0)),
        longitude=(("x", "y"), np.full((3, 3), -50.0)),
    )
    monkeypatch.setattr(
        "pab.pace.cloud.download_granule",
        lambda source, cache_dir, replace=False: tmp_path / "fake_iop.nc",
    )
    monkeypatch.setattr(nasa_giop._iop, "open_iop_local", lambda fn: ds)

    db = str(tmp_path / "pab.db")
    with Store.open(db) as store:
        _seed_matchup_with_bing_fit(store)

    log_file = str(tmp_path / "run.log")
    argv = ["--db", db, "--cache-dir", str(tmp_path), "--log-file", log_file]
    assert nasa_giop.main(argv) == 0
    with Store.open(db, create=False) as store:
        row = store.query("SELECT * FROM fits WHERE algorithm = 'NASA_GIOP'")[0]
        from pab import config

        assert row["pab_version"] == config.pab_version
    assert "nasa-giop done: written 1" in open(log_file).read()

    # resume: everything skips, still exit 0, no duplicate rows
    assert nasa_giop.main(argv) == 0
    with Store.open(db, create=False) as store:
        assert store.count("fits") == 2  # BING + one NASA_GIOP


def test_main_limit_selects_leading_slice(monkeypatch, tmp_path):
    ds = make_iop_granule()
    ds = ds.assign_coords(
        latitude=(("x", "y"), np.full((3, 3), 20.0)),
        longitude=(("x", "y"), np.full((3, 3), -50.0)),
    )
    monkeypatch.setattr(
        "pab.pace.cloud.download_granule",
        lambda source, cache_dir, replace=False: tmp_path / "fake_iop.nc",
    )
    monkeypatch.setattr(nasa_giop._iop, "open_iop_local", lambda fn: ds)

    db = str(tmp_path / "pab.db")
    with Store.open(db) as store:
        _seed_matchup_with_bing_fit(store)  # matchup 7902226_5_G1

    argv = ["--db", db, "--cache-dir", str(tmp_path)]
    assert nasa_giop.main([*argv, "--limit", "1"]) == 0
    with Store.open(db, create=False) as store:
        assert store.count("fits") == 2

    # --limit 0 selects nothing and must not error
    assert nasa_giop.main([*argv, "--limit", "0"]) == 0


def test_main_refuses_to_create_a_db(tmp_path):
    with pytest.raises(Exception):  # noqa: B017 -- Store.open(create=False) raises
        nasa_giop.main(
            ["--db", str(tmp_path / "nope.db"), "--cache-dir", str(tmp_path)]
        )
