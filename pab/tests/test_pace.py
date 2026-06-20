"""Stage 3 tests: PACE access & spectrum extraction (``pab.pace``)."""

import numpy as np
import pytest
import xarray as xr

from pab.db import Store
from pab.pace import cloud, discover, extract, flags, l1b


def make_granule(flagged=()):
    """A tiny 5x5x4 canonical granule; Rrs[i,j,:] encodes the pixel as i*10+j.

    Args:
        flagged: iterable of ``(ix, iy, flag_name)`` to set on ``l2_flags``.
    """
    nx, ny, nw = 5, 5, 4
    lat = np.linspace(44.0, 45.0, nx)
    lon = np.linspace(-31.0, -30.0, ny)
    lons2d, lats2d = np.meshgrid(lon, lat)  # shape (nx, ny)
    wave = np.array([440.0, 490.0, 550.0, 670.0])
    rrs = np.zeros((nx, ny, nw))
    for i in range(nx):
        for j in range(ny):
            rrs[i, j, :] = i * 10 + j
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


# -- flags ------------------------------------------------------------------
def test_flag_value_and_decode():
    val = flags.flag_value(["LAND", "CLDICE"])
    assert val == (1 << 1) | (1 << 9)
    assert set(flags.decode(val)) == {"LAND", "CLDICE"}


def test_is_set_and_masks_match_bits():
    l2 = np.array(
        [
            [0, flags.flag_value(["LAND"])],
            [flags.flag_value(["CHLWARN"]), flags.flag_value(["ATMFAIL"])],
        ]
    )
    assert flags.is_set(l2, "LAND").tolist() == [[False, True], [False, False]]
    # CHLWARN is not in the standard ocean mask -> that pixel stays good.
    bad = flags.flagged_mask(l2)
    assert bad.tolist() == [[False, True], [False, True]]
    assert flags.good_mask(l2).tolist() == [[True, False], [True, False]]


def test_unknown_flag_raises():
    with pytest.raises(KeyError):
        flags.is_set(np.array([0]), "NOPE")


# -- distance ---------------------------------------------------------------
def test_haversine_one_degree_lat():
    # ~111 km per degree of latitude
    d = extract.haversine_km([45.0], [-30.0], 46.0, -30.0)
    assert d[0] == pytest.approx(111.19, rel=0.01)


# -- nearest pixel & extraction ---------------------------------------------
def test_nearest_pixel_selection():
    ds = make_granule()
    lat = float(ds["latitude"].values[2, 2])
    lon = float(ds["longitude"].values[2, 2])
    px = extract.nearest_valid_pixels(ds, lat, lon, n=5)
    assert px[0]["ix"] == 2 and px[0]["iy"] == 2
    assert px[0]["rank"] == 1
    assert px[0]["distance_km"] == pytest.approx(0.0, abs=1e-6)
    assert len(px) == 5


def test_nearest_skips_flagged_pixel():
    ds = make_granule(flagged=[(2, 2, "LAND")])
    lat = float(ds["latitude"].values[2, 2])
    lon = float(ds["longitude"].values[2, 2])
    px = extract.nearest_valid_pixels(ds, lat, lon, n=3)
    # the (2,2) pixel is masked, so it must not be selected
    assert all((p["ix"], p["iy"]) != (2, 2) for p in px)
    # the nearest valid pixel is an immediate neighbour
    assert abs(px[0]["ix"] - 2) + abs(px[0]["iy"] - 2) == 1


def test_extract_spectrum_values():
    ds = make_granule()
    wave, rrs, unc = extract.extract_spectrum(ds, 3, 4)
    assert wave.tolist() == [440.0, 490.0, 550.0, 670.0]
    assert np.all(rrs == 34)  # i*10+j = 34
    assert np.allclose(unc, 3.4)


def test_extract_matchup_spectra_attaches_arrays():
    ds = make_granule()
    lat = float(ds["latitude"].values[1, 1])
    lon = float(ds["longitude"].values[1, 1])
    recs = extract.extract_matchup_spectra(ds, lat, lon, n=4)
    assert len(recs) == 4
    top = recs[0]
    assert (top["ix"], top["iy"]) == (1, 1)
    assert np.all(top["Rrs"] == 11)
    assert top["wavelength"].size == 4


def test_no_valid_pixels_returns_empty():
    ds = make_granule(flagged=[(i, j, "LAND") for i in range(5) for j in range(5)])
    px = extract.nearest_valid_pixels(ds, 44.5, -30.5)
    assert px == []


# -- cloud abstraction (mocked: no network) ---------------------------------
def test_to_granule_ds_attaches_flags():
    base = make_granule().drop_vars("l2_flags")
    l2 = np.zeros((5, 5), dtype=np.int64)
    out = cloud.to_granule_ds(base, l2)
    assert "l2_flags" in out
    assert out["l2_flags"].dims == ("x", "y")


def test_open_granule_with_injected_opener():
    ds = make_granule()
    # inject a fake opener -> exercises the abstraction without S3/ocpy
    out = cloud.open_granule("s3://bucket/g.nc", opener=lambda src: ds)
    assert out.identical(ds)


def test_open_granule_opendap_not_implemented():
    with pytest.raises(NotImplementedError):
        cloud.open_granule("s3://x", backend="opendap")


def test_open_granule_unknown_backend():
    with pytest.raises(ValueError):
        cloud.open_granule("x", backend="bogus")


# -- discovery persistence (no network) -------------------------------------
def test_persist_granules_from_table():
    import pandas as pd

    table = pd.DataFrame(
        [
            {
                "granule_id": "G1",
                "time_start": "2024-05-01T00:00:00",
                "footprint": "POLYGON((0 0,1 0,1 1,0 1,0 0))",
                "cloud_cover": 5.0,
                "data_url": "s3://b/G1.nc",
            },
            {
                "granule_id": "G2",
                "time_start": "2024-05-02T00:00:00",
                "footprint": None,
                "cloud_cover": 12.0,
                "data_url": "s3://b/G2.nc",
            },
        ]
    )
    with Store.open(":memory:") as store:
        n = discover.persist_granules(store, table)
        assert n == 2
        rows = store.query("SELECT * FROM granules ORDER BY granule_id")
        assert [r["granule_id"] for r in rows] == ["G1", "G2"]
        assert rows[0]["short_name"] == "PACE_OCI_L2_AOP"
        assert rows[0]["cloud_cover"] == 5.0
        # idempotent re-persist
        discover.persist_granules(store, table)
        assert store.count("granules") == 2


# -- noise vector (ocpy) ----------------------------------------------------
def test_pace_noise_vector():
    pytest.importorskip("ocpy")
    wave = np.array([440.0, 490.0, 550.0, 670.0])
    noise = extract.pace_noise_vector(wave)
    assert np.asarray(noise).shape[0] == wave.size


# -- L1B hook ---------------------------------------------------------------
def test_l1b_stub_raises():
    assert l1b.RRS_SOURCE_L2 == "L2_AOP"
    with pytest.raises(NotImplementedError):
        l1b.rrs_from_l1b()
