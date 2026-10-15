"""Tests for the ``geometry`` stage (:mod:`pab.matchup.geometry`).

Offline throughout. The stub opener is **module-level** (not a closure) so it
survives pickling into a spawned worker — that is what lets the parallel path
be exercised for real rather than silently falling back to serial.
"""

import numpy as np
import pytest
import xarray as xr

from pab.db import Store
from pab.matchup import geometry as geom
from pab.pace import l1b
from pab.parallel import picklable
from pab.pipeline import STAGES, PipelineConfig, run

# Angles planted per granule so a test can tell which granule a pixel read from.
GRANULE_ANGLES = {
    "PACE_OCI.20250309T131631.L2.OC_AOP.V3_2.nc": (29.47, 54.58, -19.75, 61.58),
    "PACE_OCI.20250625T030832.L2.OC_AOP.V3_2.nc": (11.0, 22.0, 5.0, -35.0),
}
NX, NY = 6, 5


def _grid():
    """Lat/lon grids shared by every synthetic granule (identical L1B/L2 grid)."""
    lat = np.linspace(-2.0, 2.0, NX)[:, None] + np.zeros((1, NY))
    lon = np.zeros((NX, 1)) + np.linspace(50.0, 54.0, NY)[None, :]
    return lat, lon


def stub_opener(source):
    """Module-level (picklable) AOP source → synthetic geolocation dataset."""
    lat, lon = _grid()
    theta_s, theta_v, solar_az, sensor_az = GRANULE_ANGLES[str(source)]
    full = np.full((NX, NY), 1.0)
    return xr.Dataset(
        {
            "latitude": (("x", "y"), lat),
            "longitude": (("x", "y"), lon),
            "solar_zenith": (("x", "y"), full * theta_s),
            "sensor_zenith": (("x", "y"), full * theta_v),
            "solar_azimuth": (("x", "y"), full * solar_az),
            "sensor_azimuth": (("x", "y"), full * sensor_az),
        }
    )


def exploding_opener(source):
    """Module-level opener that always fails — the granule-level failure path."""
    raise OSError(f"cannot open {source}")


def _seed(path, *, n_pixels=3, granules=tuple(GRANULE_ANGLES)):
    """A v5 store with one matchup per granule and ``n_pixels`` pixels each."""
    store = Store.open(path)
    store.upsert("floats", {"wmo": 6903823})
    lat, lon = _grid()
    for gi, gid in enumerate(granules):
        store.upsert("profiles", {"wmo": 6903823, "cycle": gi})
        pid = store.query("SELECT profile_id FROM profiles WHERE cycle = ?", (gi,))[0][
            "profile_id"
        ]
        store.upsert("granules", {"granule_id": gid, "data_url": gid})
        mid = f"M{gi}"
        store.upsert(
            "matchups", {"matchup_id": mid, "profile_id": pid, "granule_id": gid}
        )
        for k in range(n_pixels):
            store.upsert(
                "matchup_pixels",
                {
                    "matchup_id": mid,
                    "ix": k,
                    "iy": k,
                    "latitude": float(lat[k, k]),
                    "longitude": float(lon[k, k]),
                    "rank": k + 1,
                    "flagged": 0,
                },
            )
    return store


@pytest.fixture
def store(tmp_path):
    s = _seed(tmp_path / "v2.db")
    yield s
    s.close()


def _filled(store):
    return store.query(
        "SELECT pixel_id, theta_s, theta_v, dphi, geom_source FROM matchup_pixels "
        "WHERE theta_s IS NOT NULL ORDER BY pixel_id"
    )


# -- wiring --------------------------------------------------------------------
def test_geometry_is_a_stage_between_match_and_fit():
    assert "geometry" in STAGES
    assert STAGES.index("match") < STAGES.index("geometry") < STAGES.index("fit")


def test_dry_run_lists_geometry(store):
    out = run(store, PipelineConfig(), dry_run=True)
    assert out["stages"].index("geometry") == out["stages"].index("match") + 1


def test_cli_accepts_stage_geometry():
    from pab.pipeline import build_parser

    args = build_parser().parse_args(["--stage", "geometry", "--db", "x.db"])
    assert args.stages == ["geometry"]


def test_stage_runs_through_the_pipeline_runner(store):
    summary = run(store, PipelineConfig(), stages=["geometry"], opener=stub_opener)
    assert len(summary["geometry"]["written"]) == 6


# -- work selection -------------------------------------------------------------
def test_pixels_needing_geometry_groups_by_granule(store):
    rows = geom.pixels_needing_geometry(store)
    assert len(rows) == 6
    by_g = geom.group_by_granule(rows)
    assert set(by_g) == set(GRANULE_ANGLES)
    assert all(len(v) == 3 for v in by_g.values())


def test_source_prefers_data_url_over_granule_id(tmp_path):
    s = _seed(tmp_path / "u.db")
    s.execute(
        "UPDATE granules SET data_url = 'https://d/x.nc' WHERE granule_id = ?",
        (list(GRANULE_ANGLES)[0],),
    )
    sources = {r["source"] for r in geom.pixels_needing_geometry(s)}
    assert "https://d/x.nc" in sources
    s.close()


# -- serial fill ------------------------------------------------------------------
def test_serial_fill_writes_the_right_angles(store):
    res = geom.build_geometry(store, opener=stub_opener)
    assert len(res["written"]) == 6
    assert res["failed"] == [] and res["mismatched"] == []

    rows = store.query(
        "SELECT p.theta_s, p.theta_v, p.dphi, p.geom_source, m.granule_id "
        "FROM matchup_pixels p JOIN matchups m USING (matchup_id)"
    )
    assert len(rows) == 6
    for r in rows:
        theta_s, theta_v, solar_az, sensor_az = GRANULE_ANGLES[r["granule_id"]]
        assert r["theta_s"] == pytest.approx(theta_s)
        assert r["theta_v"] == pytest.approx(theta_v)
        assert r["dphi"] == pytest.approx(l1b.wrap_dphi(sensor_az - solar_az))
        assert r["geom_source"] == l1b.GEOM_SOURCE


def test_one_open_per_granule_not_per_pixel(store):
    """The whole point of the stage: 6 pixels, 2 granules, 2 opens."""
    calls = []

    def counting(source):
        calls.append(source)
        return stub_opener(source)

    geom.build_geometry(store, opener=counting)
    assert len(calls) == 2
    assert sorted(calls) == sorted(GRANULE_ANGLES)


# -- idempotency / resume ----------------------------------------------------------
def test_resume_does_zero_opens(store):
    geom.build_geometry(store, opener=stub_opener)

    calls = []

    def counting(source):
        calls.append(source)
        return stub_opener(source)

    res = geom.build_geometry(store, opener=counting)
    assert calls == []
    assert res["written"] == []
    assert len(res["skipped"]) == 6


def test_replace_refills(store):
    geom.build_geometry(store, opener=stub_opener)
    store.execute("UPDATE matchup_pixels SET theta_s = -1.0")
    res = geom.build_geometry(store, opener=stub_opener, replace=True)
    assert len(res["written"]) == 6
    assert all(r["theta_s"] > 0 for r in _filled(store))


def test_partial_resume_only_fills_the_gap(store):
    geom.build_geometry(store, opener=stub_opener)
    pid = _filled(store)[0]["pixel_id"]
    store.execute(
        "UPDATE matchup_pixels SET theta_s = NULL, theta_v = NULL, dphi = NULL, "
        "geom_source = NULL WHERE pixel_id = ?",
        (pid,),
    )
    calls = []

    def counting(source):
        calls.append(source)
        return stub_opener(source)

    res = geom.build_geometry(store, opener=counting)
    assert res["written"] == [pid]
    assert len(calls) == 1  # only the granule that pixel belongs to


# -- failure handling ----------------------------------------------------------------
def test_grid_check_failure_is_recorded_not_raised(store):
    """A pixel whose stored lat/lon disagrees with the L1B grid is logged."""
    pid = store.query("SELECT pixel_id FROM matchup_pixels ORDER BY pixel_id")[0][
        "pixel_id"
    ]
    store.execute(
        "UPDATE matchup_pixels SET latitude = 80.0 WHERE pixel_id = ?", (pid,)
    )

    res = geom.build_geometry(store, opener=stub_opener)  # must not raise

    assert len(res["written"]) == 5  # the granule's other pixels still filled
    assert [p for p, _ in res["mismatched"]] == [pid]
    assert "GridMismatchError" in res["mismatched"][0][1]
    assert res["failed"] == []
    still_null = store.query(
        "SELECT pixel_id FROM matchup_pixels WHERE pixel_id = ? AND theta_s IS NULL",
        (pid,),
    )
    assert len(still_null) == 1


def test_granule_failure_is_counted_and_does_not_abort(store):
    """One unreadable granule must not cost the other granule's pixels."""
    bad = list(GRANULE_ANGLES)[0]

    def flaky(source):
        if source == bad:
            raise OSError("boom")
        return stub_opener(source)

    res = geom.build_geometry(store, opener=flaky)
    assert res["failed"] == [bad]
    assert len(res["written"]) == 3  # the good granule's pixels


def test_every_granule_failing_still_returns_a_summary(store):
    res = geom.build_geometry(store, opener=exploding_opener)
    assert sorted(res["failed"]) == sorted(GRANULE_ANGLES)
    assert res["written"] == []


def test_non_finite_angles_are_recorded_as_mismatched(store):
    def nan_opener(source):
        ds = stub_opener(source)
        ds["solar_zenith"][0, 0] = np.nan
        return ds

    res = geom.build_geometry(store, opener=nan_opener)
    assert len(res["mismatched"]) == 2  # pixel (0,0) of each granule
    assert all("non-finite" in reason for _, reason in res["mismatched"])
    assert len(res["written"]) == 4


def test_nothing_to_do_is_not_an_error(tmp_path):
    s = Store.open(tmp_path / "empty.db")
    res = geom.build_geometry(s, opener=stub_opener)
    assert res == {"written": [], "skipped": [], "failed": [], "mismatched": []}
    s.close()


# -- parallel -----------------------------------------------------------------------
def test_stub_opener_is_picklable():
    """Guards the precondition for the parallel test below being meaningful."""
    assert picklable(stub_opener)
    assert not picklable(lambda s: s)


def test_parallel_agrees_with_serial(tmp_path):
    serial = _seed(tmp_path / "serial.db")
    parallel = _seed(tmp_path / "parallel.db")
    try:
        r1 = geom.build_geometry(serial, opener=stub_opener, jobs=1)
        r2 = geom.build_geometry(parallel, opener=stub_opener, jobs=2)
        assert sorted(r2["written"]) == sorted(r1["written"])
        assert r2["failed"] == r1["failed"] == []
        assert _filled(parallel) == _filled(serial)
    finally:
        serial.close()
        parallel.close()


def test_parallel_records_a_failed_granule(tmp_path):
    s = _seed(tmp_path / "pf.db")
    try:
        res = geom.build_geometry(s, opener=exploding_opener, jobs=2)
        assert sorted(res["failed"]) == sorted(GRANULE_ANGLES)
        assert res["written"] == []
    finally:
        s.close()


def test_unpicklable_opener_falls_back_to_serial(store):
    """A closure opener must still work, just serially — never fail every granule."""
    res = geom.build_geometry(store, opener=lambda s: stub_opener(s), jobs=4)
    assert len(res["written"]) == 6
    assert res["failed"] == []
