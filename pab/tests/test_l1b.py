"""Tests for :mod:`pab.pace.l1b` — per-pixel viewing geometry from PACE L1B.

Offline throughout, against a **synthetic geolocation dataset** shaped like a
real L1B ``geolocation_data`` group. One live test at the end reproduces the
verified reference numbers and is skipped unless ``PAB_LIVE_L1B=1``.
"""

import os

import numpy as np
import pytest
import xarray as xr

from pab.pace import l1b

AOP = "PACE_OCI.20250309T131631.L2.OC_AOP.V3_2.nc"
AOP_URL = f"https://obdaac-tea.earthdatacloud.nasa.gov/ob-cumulus-prod/{AOP}"
L1B_NAME = "PACE_OCI.20250309T131631.L1B.V3.nc"

#: The verified reference pixel and its angles (see the module docstring).
REF_IX, REF_IY = 868, 142
REF_THETA_S, REF_THETA_V = 29.47, 54.58
REF_SOLAR_AZ, REF_SENSOR_AZ = -19.75, 61.58
REF_DPHI = 81.33


def synthetic_geolocation(nx=12, ny=8, *, dims=("x", "y")):
    """A geolocation dataset shaped like L1B's, with known values per pixel.

    ``latitude``/``longitude`` vary smoothly so a wrong index is detectable,
    and the reference pixel's angles are planted at ``(2, 3)``.
    """
    lat = np.linspace(-10.0, 10.0, nx)[:, None] + np.zeros((1, ny))
    lon = np.zeros((nx, 1)) + np.linspace(100.0, 120.0, ny)[None, :]
    solar_z = np.full((nx, ny), 20.0)
    sensor_z = np.full((nx, ny), 40.0)
    solar_a = np.full((nx, ny), 10.0)
    sensor_a = np.full((nx, ny), 50.0)
    if nx > 2 and ny > 3:  # the planted reference pixel needs the room
        solar_z[2, 3], sensor_z[2, 3] = REF_THETA_S, REF_THETA_V
        solar_a[2, 3], sensor_a[2, 3] = REF_SOLAR_AZ, REF_SENSOR_AZ
    return xr.Dataset(
        {
            "latitude": (dims, lat),
            "longitude": (dims, lon),
            "solar_zenith": (dims, solar_z),
            "sensor_zenith": (dims, sensor_z),
            "solar_azimuth": (dims, solar_a),
            "sensor_azimuth": (dims, sensor_a),
        }
    )


@pytest.fixture
def geo():
    return synthetic_geolocation()


# -- the three exported symbols the old stub had must survive -----------------
def test_module_keeps_its_rrs_hook_symbols():
    assert l1b.RRS_SOURCE_L2 == "L2_AOP"
    assert l1b.RRS_SOURCE_PREFIX == "PAB_L1B"
    with pytest.raises(NotImplementedError):
        l1b.rrs_from_l1b()


# -- name swap ----------------------------------------------------------------
@pytest.mark.parametrize("source", [AOP, AOP_URL])
def test_l1b_name_for_aop(source):
    assert l1b.l1b_name_for_aop(source) == L1B_NAME


def test_l1b_name_drops_the_aop_minor_version():
    """``V3_2`` (AOP) and ``V3_1`` both map to the L1B's ``V3``."""
    v1 = "PACE_OCI.20240926T065355.L2.OC_AOP.V3_1.nc"
    assert l1b.l1b_name_for_aop(v1) == "PACE_OCI.20240926T065355.L1B.V3.nc"


def test_granule_stamp():
    assert l1b.granule_stamp(AOP_URL) == "20250309T131631"


@pytest.mark.parametrize(
    "bad",
    [
        "PACE_OCI.20250309T131631.L2.OC_IOP.V3_2.nc",  # IOP, not AOP
        "PACE_OCI.20250309T131631.L1B.V3.nc",  # already L1B
        "not-a-granule.nc",
    ],
)
def test_non_aop_sources_raise(bad):
    with pytest.raises(ValueError, match="AOP"):
        l1b.l1b_name_for_aop(bad)
    with pytest.raises(ValueError, match="AOP"):
        l1b.granule_stamp(bad)


# -- CMR resolution -----------------------------------------------------------
class _FakeGranule:
    def __init__(self, *urls):
        self._urls = urls

    def data_links(self):
        return list(self._urls)


def test_l1b_source_for_aop_resolves_and_dedupes():
    """CMR lists each granule twice; the search is windowed on the stamp."""
    url = f"https://d.example/{L1B_NAME}"
    seen = {}

    def fake_search(*, short_name, temporal):
        seen["short_name"] = short_name
        seen["temporal"] = temporal
        # the same granule twice, as CMR really returns it
        return [_FakeGranule(url), _FakeGranule(url)]

    assert l1b.l1b_source_for_aop(AOP_URL, search=fake_search) == url
    assert seen["short_name"] == l1b.L1B_SHORT_NAME
    start, end = seen["temporal"]
    assert start == "2025-03-09T13:15:31Z"
    assert end == "2025-03-09T13:17:31Z"


def test_l1b_source_for_aop_picks_the_matching_name():
    """A window can return neighbouring overpasses; only the stamp match wins."""
    other = "https://d.example/PACE_OCI.20250309T131000.L1B.V3.nc"
    want = f"https://d.example/{L1B_NAME}"

    def fake_search(**_):
        return [_FakeGranule(other), _FakeGranule(want, other)]

    assert l1b.l1b_source_for_aop(AOP, search=fake_search) == want


def test_l1b_source_for_aop_raises_when_absent():
    def fake_search(**_):
        return [_FakeGranule("https://d.example/PACE_OCI.20200101T000000.L1B.V3.nc")]

    with pytest.raises(FileNotFoundError, match="no PACE_OCI_L1B_SCI granule"):
        l1b.l1b_source_for_aop(AOP, search=fake_search)


def test_malformed_cmr_result_is_skipped_not_fatal():
    class _Broken:
        def data_links(self):
            raise RuntimeError("bad result")

    want = f"https://d.example/{L1B_NAME}"

    def fake_search(**_):
        return [_Broken(), _FakeGranule(want)]

    assert l1b.l1b_source_for_aop(AOP, search=fake_search) == want


# -- dphi wrapping -------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (81.33, 81.33),
        (0.0, 0.0),
        (180.0, 180.0),
        (-180.0, 180.0),  # the half-open end: (-180, 180]
        (181.0, -179.0),
        (-181.0, 179.0),
        (360.0, 0.0),
        (-359.0, 1.0),
    ],
)
def test_wrap_dphi(raw, expected):
    assert l1b.wrap_dphi(raw) == pytest.approx(expected)


def test_wrap_dphi_matches_the_reference_pixel():
    assert l1b.wrap_dphi(REF_SENSOR_AZ - REF_SOLAR_AZ) == pytest.approx(REF_DPHI)


# -- reading the group ----------------------------------------------------------
def test_read_geolocation_renames_dims(tmp_path):
    """L1B's ``(scans, pixels)`` become PAB's canonical ``(x, y)``."""
    path = tmp_path / "l1b.nc"
    dt = xr.DataTree.from_dict(
        {l1b.GEOLOCATION_GROUP: synthetic_geolocation(dims=("scans", "pixels"))}
    )
    dt.to_netcdf(path, engine="h5netcdf")

    ds = l1b.read_geolocation(str(path))
    assert set(ds.sizes) == {"x", "y"}
    assert set(l1b.ANGLE_VARS) <= set(ds.data_vars)


def test_read_geolocation_rejects_a_granule_without_the_group(tmp_path):
    path = tmp_path / "wrong.nc"
    xr.DataTree.from_dict(
        {"geophysical_data": xr.Dataset({"a": ("x", [1.0])})}
    ).to_netcdf(path, engine="h5netcdf")
    with pytest.raises(KeyError, match="geolocation_data"):
        l1b.read_geolocation(str(path))


def test_open_l1b_geolocation_uses_the_opener_seam(geo):
    calls = []

    def opener(source):
        calls.append(source)
        return geo

    ds = l1b.open_l1b_geolocation("s3://bucket/x.nc", opener=opener)
    assert ds is geo
    assert calls == ["s3://bucket/x.nc"]


def test_open_l1b_geolocation_is_bounded_by_the_timeout():
    import time

    def slow(source):
        time.sleep(3)

    with pytest.raises(TimeoutError, match="granule read exceeded"):
        l1b.open_l1b_geolocation("s3://bucket/x.nc", opener=slow, timeout_s=1)


# -- pixel_geometry -------------------------------------------------------------
def test_pixel_geometry_returns_the_planted_angles(geo):
    lat = float(geo["latitude"].isel(x=2, y=3).values)
    lon = float(geo["longitude"].isel(x=2, y=3).values)
    theta_s, theta_v, dphi = l1b.pixel_geometry(geo, 2, 3, lat=lat, lon=lon)
    assert theta_s == pytest.approx(REF_THETA_S)
    assert theta_v == pytest.approx(REF_THETA_V)
    assert dphi == pytest.approx(REF_DPHI)


def test_pixel_geometry_grid_check_rejects_a_shifted_pixel(geo):
    """The classic silent failure: right index, wrong grid."""
    lat = float(geo["latitude"].isel(x=5, y=3).values)
    lon = float(geo["longitude"].isel(x=5, y=3).values)
    with pytest.raises(l1b.GridMismatchError, match="dlat"):
        l1b.pixel_geometry(geo, 2, 3, lat=lat, lon=lon)


def test_pixel_geometry_grid_check_catches_a_longitude_shift(geo):
    lat = float(geo["latitude"].isel(x=2, y=3).values)
    lon = float(geo["longitude"].isel(x=2, y=6).values)
    with pytest.raises(l1b.GridMismatchError, match="dlon"):
        l1b.pixel_geometry(geo, 2, 3, lat=lat, lon=lon)


def test_pixel_geometry_tolerance_is_honoured(geo):
    """Within tol passes; the same offset with a tighter tol raises."""
    lat = float(geo["latitude"].isel(x=2, y=3).values)
    lon = float(geo["longitude"].isel(x=2, y=3).values)
    l1b.pixel_geometry(geo, 2, 3, lat=lat + 0.005, lon=lon, tol_deg=0.01)
    with pytest.raises(l1b.GridMismatchError):
        l1b.pixel_geometry(geo, 2, 3, lat=lat + 0.005, lon=lon, tol_deg=0.001)


def test_pixel_geometry_grid_check_handles_the_antimeridian():
    """179.99 and -179.99 are 0.02° apart, not 359.98°."""
    ds = synthetic_geolocation(nx=4, ny=4)
    ds["longitude"][:] = 179.99
    ds["latitude"][:] = 0.0
    # must not raise: the wrapped separation is 0.02 deg
    l1b.pixel_geometry(ds, 1, 1, lat=0.0, lon=-179.99, tol_deg=0.05)


def test_pixel_geometry_rejects_non_finite_angles(geo):
    geo["solar_zenith"][2, 3] = np.nan
    lat = float(geo["latitude"].isel(x=2, y=3).values)
    lon = float(geo["longitude"].isel(x=2, y=3).values)
    with pytest.raises(ValueError, match="non-finite"):
        l1b.pixel_geometry(geo, 2, 3, lat=lat, lon=lon)


# -- live ------------------------------------------------------------------------
@pytest.mark.skipif(
    os.environ.get("PAB_LIVE_L1B") != "1",
    reason="live PACE L1B read; set PAB_LIVE_L1B=1 to run",
)
def test_live_reference_granule_reproduces_the_verified_numbers():
    """End-to-end against the real granule: CMR → open → pixel_geometry.

    Reproduces the 2026-09-14 verification: ``PACE_OCI.20250309T131631`` at
    pixel (868, 142) → theta_s 29.47, theta_v 54.58, dphi 81.33.
    """
    url = l1b.l1b_source_for_aop(AOP)
    assert url.endswith(L1B_NAME)

    ds = l1b.open_l1b_geolocation(url)
    try:
        assert ds.sizes["x"] == 1709
        assert ds.sizes["y"] == 1272
        lat = float(ds["latitude"].isel(x=REF_IX, y=REF_IY).values)
        lon = float(ds["longitude"].isel(x=REF_IX, y=REF_IY).values)
        theta_s, theta_v, dphi = l1b.pixel_geometry(
            ds, REF_IX, REF_IY, lat=lat, lon=lon
        )
    finally:
        ds.close()

    assert theta_s == pytest.approx(REF_THETA_S, abs=0.01)
    assert theta_v == pytest.approx(REF_THETA_V, abs=0.01)
    assert dphi == pytest.approx(REF_DPHI, abs=0.01)
