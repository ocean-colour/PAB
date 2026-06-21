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
