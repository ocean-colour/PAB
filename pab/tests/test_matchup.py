"""Stage 4 tests: the space + time matchup engine (``pab.matchup``)."""

import numpy as np
import pytest
import xarray as xr

from pab.argo.summary import persist_summary
from pab.db import Store
from pab.matchup import engine
from pab.pace import flags


def make_granule(center=(44.5, -30.5), span=0.5, flagged=()):
    """A tiny 5x5x4 canonical granule centered on ``center`` (lat, lon).

    ``Rrs[i, j, :]`` encodes the pixel as ``i*10 + j`` (as in the Stage 3
    fixture). ``flagged`` is an iterable of ``(ix, iy, flag_name)``.
    """
    nx, ny, nw = 5, 5, 4
    clat, clon = center
    lat = np.linspace(clat - span, clat + span, nx)
    lon = np.linspace(clon - span, clon + span, ny)
    lons2d, lats2d = np.meshgrid(lon, lat)  # (nx, ny)
    wave = np.array([440.0, 490.0, 550.0, 670.0])
    rrs = np.fromfunction(lambda i, j, k: i * 10 + j, (nx, ny, nw))
    l2 = np.zeros((nx, ny), dtype=np.int64)
    for ix, iy, name in flagged:
        l2[ix, iy] |= flags.flag_value([name])
    return xr.Dataset(
        {
            "Rrs": (("x", "y", "wl"), rrs),
            "Rrs_unc": (("x", "y", "wl"), rrs * 0.1),
            "l2_flags": (("x", "y"), l2),
        },
        coords={
            "latitude": (("x", "y"), lats2d),
            "longitude": (("x", "y"), lons2d),
            "wavelength": ("wl", wave),
        },
    )


# -- pure helpers -----------------------------------------------------------
def test_make_matchup_id():
    assert engine.make_matchup_id(7902226, 5, "G1") == "7902226_5_G1"


def test_time_offset_hours_and_parsing():
    # 90 minutes apart -> 1.5 h, regardless of arg order or a trailing Z
    assert engine.time_offset_hours(
        "2025-02-18T12:00:00", "2025-02-18T10:30:00"
    ) == pytest.approx(1.5)
    assert engine.time_offset_hours(
        "2025-02-18T10:30:00Z", "2025-02-18T12:00:00"
    ) == pytest.approx(1.5)


# -- spatial / temporal matching --------------------------------------------
def _profile(lat, lon, time, **extra):
    base = {"wmo": 7902226, "cycle": 5, "latitude": lat, "longitude": lon, "time": time}
    base.update(extra)
    return base


def test_find_matchup_selects_closest_granule():
    # Two granules in time: one centered on the float, one offset ~1 deg away.
    near = make_granule(center=(20.0, -50.0))
    far = make_granule(center=(21.0, -50.0))
    openers = {"near": near, "far": far}
    prof = _profile(20.0, -50.0, "2025-05-01T12:00:00")
    candidates = [
        {"granule_id": "GN", "time": "2025-05-01T11:00:00", "source": "near"},
        {"granule_id": "GF", "time": "2025-05-01T12:30:00", "source": "far"},
    ]
    m = engine.find_matchup(
        prof, candidates, opener=lambda s: openers[s], config=engine.MatchupConfig()
    )
    assert m is not None
    assert m.granule_id == "GN"  # nearest in space wins
    assert m.distance_km == pytest.approx(0.0, abs=1e-6)
    assert m.dtime_hours == pytest.approx(1.0)
    assert m.n_spectra == 10


def test_find_matchup_time_window_edge():
    ds = make_granule(center=(20.0, -50.0))
    prof = _profile(20.0, -50.0, "2025-05-01T12:00:00")
    cfg = engine.MatchupConfig(dtime_max_hours=3.0)

    just_inside = [
        {"granule_id": "G", "time": "2025-05-01T09:00:00", "source": "s"}
    ]  # exactly 3.0 h
    assert engine.find_matchup(prof, just_inside, opener=lambda s: ds, config=cfg)

    just_outside = [
        {"granule_id": "G", "time": "2025-05-01T08:59:00", "source": "s"}
    ]  # 3.0167 h
    assert (
        engine.find_matchup(prof, just_outside, opener=lambda s: ds, config=cfg) is None
    )


def test_find_matchup_distance_gate_rejects_far_footprint():
    # Granule footprint is ~1.5 deg (~165 km) from the float -> beyond the gate.
    ds = make_granule(center=(30.0, -50.0))
    prof = _profile(20.0, -50.0, "2025-05-01T12:00:00")
    cands = [{"granule_id": "G", "time": "2025-05-01T12:00:00", "source": "s"}]
    assert engine.find_matchup(prof, cands, opener=lambda s: ds) is None


def test_find_matchup_excludes_flagged_nearest_pixel():
    # The float sits on pixel (2,2); flag it -> a neighbour becomes nearest.
    ds = make_granule(center=(20.0, -50.0), flagged=[(2, 2, "LAND")])
    lat = float(ds["latitude"].values[2, 2])
    lon = float(ds["longitude"].values[2, 2])
    prof = _profile(lat, lon, "2025-05-01T12:00:00")
    cands = [{"granule_id": "G", "time": "2025-05-01T12:00:00", "source": "s"}]
    # the synthetic grid spacing is ~26 km/pixel, so loosen the distance gate
    cfg = engine.MatchupConfig(max_distance_km=50.0)
    m = engine.find_matchup(prof, cands, opener=lambda s: ds, config=cfg)
    assert m is not None
    assert all((px["ix"], px["iy"]) != (2, 2) for px in m.pixels)
    assert all(px["flagged"] == 0 for px in m.pixels)  # selected pixels are unflagged


def test_find_matchup_all_flagged_returns_none():
    ds = make_granule(
        center=(20.0, -50.0),
        flagged=[(i, j, "LAND") for i in range(5) for j in range(5)],
    )
    prof = _profile(20.0, -50.0, "2025-05-01T12:00:00")
    cands = [{"granule_id": "G", "time": "2025-05-01T12:00:00", "source": "s"}]
    assert engine.find_matchup(prof, cands, opener=lambda s: ds) is None


# -- persistence ------------------------------------------------------------
def _seed_store(store, *, profile_lat=20.0, profile_lon=-50.0):
    """Persist a qualifying profile and one granule; return the profile dict."""
    pid = persist_summary(
        store,
        wmo=7902226,
        cycle=5,
        summary={"mld": 30.0, "mld_method": "x", "n_points": 5},
        latitude=profile_lat,
        longitude=profile_lon,
        time="2025-05-01T12:00:00",
    )
    store.upsert(
        "granules",
        {
            "granule_id": "G1",
            "time_start": "2025-05-01T11:30:00",
            "data_url": "s3://b/G1.nc",
        },
    )
    return pid


def test_build_matchups_persists_links_and_is_idempotent():
    ds = make_granule(center=(20.0, -50.0))
    with Store.open(":memory:") as store:
        pid = _seed_store(store)
        out = engine.build_matchups(store, opener=lambda s: ds)
        assert out["written"] == ["7902226_5_G1"]

        m = store.query("SELECT * FROM matchups")[0]
        assert m["profile_id"] == pid
        assert m["granule_id"] == "G1"
        assert m["n_spectra"] == 10
        assert m["dtime_hours"] == pytest.approx(0.5)
        assert m["distance_km"] == pytest.approx(0.0, abs=1e-6)
        assert m["pab_version"] and m["created"]

        pix = store.query(
            "SELECT * FROM matchup_pixels WHERE matchup_id = ?", ("7902226_5_G1",)
        )
        assert len(pix) == 10
        assert pix[0]["matchup_id"] == "7902226_5_G1"  # FK back to the matchup
        assert {p["rank"] for p in pix} == set(range(1, 11))

        # idempotent re-run: skipped, no duplicate rows
        out2 = engine.build_matchups(store, opener=lambda s: ds)
        assert out2["written"] == [] and out2["skipped"] == ["7902226_5_G1"]
        assert store.count("matchups") == 1
        assert store.count("matchup_pixels") == 10


def test_build_matchups_unmatched_when_out_of_window():
    ds = make_granule(center=(20.0, -50.0))
    with Store.open(":memory:") as store:
        _seed_store(store)
        # tighten the window so the 0.5 h granule no longer qualifies
        cfg = engine.MatchupConfig(dtime_max_hours=0.1)
        out = engine.build_matchups(store, opener=lambda s: ds, config=cfg)
        assert out["written"] == []
        assert out["unmatched"] == ["7902226_5"]
        assert store.count("matchups") == 0


def test_find_matchup_requires_position():
    # a profile with no lat/lon cannot be matched -> clear error, not a TypeError
    prof = {
        "wmo": 7902226,
        "cycle": 5,
        "latitude": None,
        "longitude": None,
        "time": "2025-05-01T12:00:00",
    }
    cands = [{"granule_id": "G", "time": "2025-05-01T12:00:00", "source": "s"}]
    with pytest.raises(ValueError, match="no .*latitude"):
        engine.find_matchup(prof, cands, opener=lambda s: make_granule())


def test_build_matchups_skips_profile_without_position():
    ds = make_granule(center=(20.0, -50.0))
    with Store.open(":memory:") as store:
        # qualifying profile (has a summary) but with a NULL position
        persist_summary(
            store,
            wmo=7902226,
            cycle=5,
            summary={"mld": 30.0, "mld_method": "x", "n_points": 5},
            latitude=None,
            longitude=None,
            time="2025-05-01T12:00:00",
        )
        store.upsert(
            "granules",
            {
                "granule_id": "G1",
                "time_start": "2025-05-01T11:30:00",
                "data_url": "s3://b/G1.nc",
            },
        )
        out = engine.build_matchups(store, opener=lambda s: ds)
        assert out["written"] == []
        assert out["unmatched"] == ["7902226_5"]
        assert store.count("matchups") == 0


def test_write_matchup_requires_profile_id():
    m = engine.Matchup(
        matchup_id="x",
        granule_id="G",
        distance_km=0.0,
        dtime_hours=0.0,
        n_spectra=0,
        pixels=[],
        profile_id=None,
    )
    with Store.open(":memory:") as store:
        with pytest.raises(ValueError):
            engine.write_matchup(store, m)


# -- candidate pre-filter (footprint) ---------------------------------------
_POLY = "POLYGON ((-130.06 4.46, -133.13 22.33, -158.25 17.15, -153.79 -0.59, -130.06 4.46))"


def test_footprint_bbox_parses_polygon():
    assert engine.footprint_bbox(_POLY) == pytest.approx(
        (-158.25, -0.59, -130.06, 22.33)
    )


def test_footprint_bbox_widens_longitude_when_it_wraps():
    # a polar/antimeridian swath: keep the latitude band, drop the lon bound
    poly = "POLYGON ((-179 62, 179 65, 170 80, -170 78, -179 62))"
    lon_min, lat_min, lon_max, lat_max = engine.footprint_bbox(poly)
    assert (lon_min, lon_max) == (-180.0, 180.0)
    assert (lat_min, lat_max) == pytest.approx((62.0, 80.0))


def test_footprint_bbox_unknown_is_none_and_covers_everything():
    for bad in (None, "", "POLYGON EMPTY", "POLYGON ((1 2, 3 4))"):
        assert engine.footprint_bbox(bad) is None
    assert engine.footprint_covers(None, 0.0, 0.0) is True


def test_candidate_granules_filters_on_footprint():
    """A granule whose swath is elsewhere must not be offered to the profile.

    Opening a granule is the expensive step at scale (~4.4 s in-cloud), so the
    pre-filter has to exclude same-time granules over a different ocean.
    """
    far = "POLYGON ((10 40, 20 40, 20 50, 10 50, 10 40))"
    with Store.open(":memory:") as store:
        for gid, poly in (("near", _POLY), ("far", far)):
            store.upsert(
                "granules",
                {
                    "granule_id": gid,
                    "time_start": "2025-05-01T11:30:00",
                    "footprint": poly,
                    "data_url": f"s3://b/{gid}.nc",
                },
            )
        t = "2025-05-01T12:00:00"
        # inside the _POLY swath (N Pacific)
        got = engine.candidate_granules(
            store, t, dtime_max_hours=24.0, latitude=10.0, longitude=-145.0
        )
        assert [c["granule_id"] for c in got] == ["near"]
        # no position given -> time-only, both offered (back-compatible)
        assert len(engine.candidate_granules(store, t, dtime_max_hours=24.0)) == 2
        # outside both swaths -> nothing
        assert engine.candidate_granules(
            store, t, dtime_max_hours=24.0, latitude=-40.0, longitude=100.0
        ) == []


def test_granule_index_respects_the_time_window():
    with Store.open(":memory:") as store:
        for gid, t in (("g_in", "2025-05-01T11:30:00"), ("g_out", "2025-05-03T11:30:00")):
            store.upsert("granules", {"granule_id": gid, "time_start": t})
        idx = engine.GranuleIndex.load(store)
        assert len(idx) == 2
        got = idx.candidates("2025-05-01T12:00:00", dtime_max_hours=24.0)
        assert [c["granule_id"] for c in got] == ["g_in"]
        # source falls back to the granule id when there is no data_url
        assert got[0]["source"] == "g_in"


# -- parallel matching ------------------------------------------------------
def _stub_opener(source):  # module-level -> picklable, so spawned workers can use it
    return make_granule(center=(20.0, -50.0))


def test_build_matchups_parallel_matches_serial(tmp_path):
    """The parallel path must persist exactly what the serial path does.

    Exercises the real ProcessPoolExecutor (spawn) with a picklable opener, so
    the fan-out used for the production run is actually run in the test suite.
    """
    with Store.open(tmp_path / "par.db") as store:
        _seed_store(store)
        out = engine.build_matchups(store, opener=_stub_opener, jobs=2)
        assert out["written"] == ["7902226_5_G1"]
        assert store.count("matchup_pixels") == 10
        # resumable: a second parallel pass skips it, no duplicate rows
        again = engine.build_matchups(store, opener=_stub_opener, jobs=2)
        assert again["written"] == [] and again["skipped"] == ["7902226_5_G1"]
        assert store.count("matchups") == 1

    with Store.open(tmp_path / "ser.db") as store:
        _seed_store(store)
        serial = engine.build_matchups(store, opener=_stub_opener, jobs=1)
    assert serial["written"] == out["written"]


def test_build_matchups_falls_back_to_serial_for_an_unpicklable_opener():
    ds = make_granule(center=(20.0, -50.0))
    with Store.open(":memory:") as store:
        _seed_store(store)
        # a lambda cannot cross a spawn boundary -> must still produce the matchup
        out = engine.build_matchups(store, opener=lambda s: ds, jobs=4)
        assert out["written"] == ["7902226_5_G1"]


def test_build_matchups_resume_skips_before_opening_granules():
    """A resumed match must not re-open granules for profiles already matched.

    The existence check used to run *after* find_matchup, so a restart paid the
    full granule-read cost again — 15 min of wasted I/O on a 1000-profile rerun,
    and the dominant cost of any restart at 54k.
    """
    ds = make_granule(center=(20.0, -50.0))
    opens = []

    def counting_opener(source):
        opens.append(source)
        return ds

    with Store.open(":memory:") as store:
        _seed_store(store)
        first = engine.build_matchups(store, opener=counting_opener)
        assert first["written"] == ["7902226_5_G1"]
        n_first = len(opens)
        assert n_first > 0  # the first pass must actually read the granule

        opens.clear()
        again = engine.build_matchups(store, opener=counting_opener)
        assert again["skipped"] == ["7902226_5_G1"]
        assert again["written"] == []
        assert opens == []  # <- the point: zero granule opens on resume

        # --replace still re-does the work
        opens.clear()
        forced = engine.build_matchups(store, opener=counting_opener, replace=True)
        assert forced["written"] == ["7902226_5_G1"]
        assert len(opens) == n_first


def _hanging_opener(source):
    """Module-level (picklable) opener that never returns for one granule.

    Stands in for the real failure: a granule read that wedges inside a C-level
    lock with no timeout of its own.
    """
    import time

    if source == "s3://b/HANG.nc":
        time.sleep(3600)
    return make_granule(center=(20.0, -50.0))


def test_build_matchups_survives_a_wedged_worker(tmp_path):
    """A hung granule read must not hang the stage.

    On a real run all 16 workers ended up blocked with zero sockets and 0% CPU,
    and match sat dead for 40 min. The parent now kills a chunk that produces no
    result within stall_timeout_s and carries on.
    """
    with Store.open(tmp_path / "hang.db") as store:
        # one profile whose granule hangs; nothing else in the chunk
        pid = persist_summary(
            store,
            wmo=7902226,
            cycle=5,
            summary={"mld": 30.0, "mld_method": "x", "n_points": 5},
            latitude=20.0,
            longitude=-50.0,
            time="2025-05-01T12:00:00",
        )
        assert pid
        store.upsert(
            "granules",
            {
                "granule_id": "HANG",
                "time_start": "2025-05-01T11:30:00",
                "data_url": "s3://b/HANG.nc",
            },
        )
        cfg = engine.MatchupConfig(stall_timeout_s=3.0)
        out = engine.build_matchups(
            store, opener=_hanging_opener, config=cfg, jobs=2
        )
        # returned rather than hanging, and the profile is reported as stalled
        assert out["stalled"] == ["7902226_5"]
        assert out["written"] == []
        assert store.count("matchups") == 0  # retried on the next run
