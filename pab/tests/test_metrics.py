"""Stage 6 tests: comparison metrics & figures (``pab.metrics``, ``pab.plotting``)."""

import numpy as np
import pytest
import xarray as xr

from pab.argo.summary import persist_summary
from pab.db import Store
from pab.metrics import compare
from pab.pace import flags
from pab.plotting import population, scene


def make_granule(center=(20.0, -50.0), span=0.5, nwave=31, flagged=()):
    """A synthetic canonical granule on a 400–700 nm grid (decreasing Rrs)."""
    nx = ny = 5
    clat, clon = center
    lat = np.linspace(clat - span, clat + span, nx)
    lon = np.linspace(clon - span, clon + span, ny)
    lons2d, lats2d = np.meshgrid(lon, lat)
    wave = np.linspace(400.0, 700.0, nwave)
    spec = 0.01 * np.exp(-(wave - 400.0) / 150.0)  # smooth, blue-bright
    rrs = np.tile(spec, (nx, ny, 1))
    l2 = np.zeros((nx, ny), dtype=np.int64)
    for ix, iy, name in flagged:
        l2[ix, iy] |= flags.flag_value([name])
    return xr.Dataset(
        {
            "Rrs": (("x", "y", "wl"), rrs),
            "Rrs_unc": (("x", "y", "wl"), rrs * 0.05),
            "l2_flags": (("x", "y"), l2),
        },
        coords={
            "latitude": (("x", "y"), lats2d),
            "longitude": (("x", "y"), lons2d),
            "wavelength": ("wl", wave),
        },
    )


# -- pure metrics -----------------------------------------------------------
def test_log_comparison_known_values():
    stats = compare.log_comparison([2.0, 4.0, 6.0], [1.0, 2.0, 3.0])
    assert stats["n"] == 3
    assert stats["median_ratio"] == pytest.approx(2.0)
    assert stats["log_bias"] == pytest.approx(np.log10(2.0))
    assert stats["log_rms"] == pytest.approx(np.log10(2.0))
    assert stats["log_mad"] == pytest.approx(0.0, abs=1e-12)
    assert stats["spearman"] == pytest.approx(1.0)


def test_log_comparison_drops_nonpositive_and_nan():
    stats = compare.log_comparison([1.0, np.nan, -1.0, 3.0], [1.0, 2.0, 1.0, 1.0])
    assert stats["n"] == 2  # only the 1/1 and 3/1 pairs survive
    stats0 = compare.log_comparison([np.nan], [np.nan])
    assert stats0["n"] == 0 and np.isnan(stats0["median_ratio"])


def test_season_and_region():
    assert compare.season_of(1) == "DJF" and compare.season_of(7) == "JJA"
    assert compare.region_of(10.0) == "tropics"
    assert compare.region_of(27.5) == "subtropics"
    assert compare.region_of(-60.0) == "polar"


# -- store gatherers --------------------------------------------------------
def _seed(
    store,
    matchup_id,
    wmo,
    cycle,
    *,
    lat,
    lon,
    time,
    bbp_argo,
    chla,
    bbp_bing,
    chl_bing=None,
):
    pid = persist_summary(
        store,
        wmo=wmo,
        cycle=cycle,
        summary={
            "mld": 30.0,
            "mld_method": "x",
            "bbp700": bbp_argo,
            "chla": chla,
            "n_points": 6,
        },
        latitude=lat,
        longitude=lon,
        time=time,
    )
    gid = f"G_{cycle}"
    store.upsert("granules", {"granule_id": gid, "data_url": f"s3://b/{gid}.nc"})
    store.upsert(
        "matchups",
        {
            "matchup_id": matchup_id,
            "profile_id": pid,
            "granule_id": gid,
            "n_spectra": 1,
        },
    )
    store.upsert(
        "matchup_pixels",
        {"matchup_id": matchup_id, "ix": 2, "iy": 2, "rank": 1, "flagged": 0},
    )
    fit_id = f"{matchup_id}_2_2_ExpBPow"
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "algorithm": "BING",
            "model_pair": "ExpBPow",
            "chisq": 1.1,
            "pab_version": "0",
            "wave_min": 400.0,
            "wave_max": 700.0,
            "nsteps": 1000,
        },
    )
    store.upsert(
        "fit_results",
        {
            "fit_id": fit_id,
            "quantity": "BING_ExpBPow_bbp700",
            "value": bbp_bing,
            "value_lo": bbp_bing * 0.9,
            "value_hi": bbp_bing * 1.1,
            "unit": "m^-1",
        },
    )
    if chl_bing is not None:
        store.upsert(
            "fit_results",
            {
                "fit_id": fit_id,
                "quantity": "BING_ExpBPow_chl",
                "value": chl_bing,
                "value_lo": chl_bing * 0.9,
                "value_hi": chl_bing * 1.1,
                "unit": "mg m^-3",
            },
        )
    return pid


def test_gather_matchups_and_compare():
    with Store.open(":memory:") as store:
        _seed(
            store,
            "M1",
            7902226,
            5,
            lat=27.0,
            lon=-46.0,
            time="2025-02-18T20:00:00",
            bbp_argo=1e-3,
            chla=0.1,
            bbp_bing=2e-3,
            chl_bing=0.15,
        )
        _seed(
            store,
            "M2",
            7902136,
            8,
            lat=4.0,
            lon=-137.0,
            time="2025-07-25T13:00:00",
            bbp_argo=2e-3,
            chla=0.2,
            bbp_bing=4e-3,
            chl_bing=0.3,
        )
        df = compare.gather_matchups(store)
        assert len(df) == 2
        assert set(df["matchup_id"]) == {"M1", "M2"}
        # bbp_bing is 2x bbp_argo for both -> median ratio 2
        stats = compare.compare(df, "bbp_bing", "bbp_argo")
        assert stats["median_ratio"] == pytest.approx(2.0)
        # chl_bing is 1.5x the Argo chla for both -> median ratio 1.5
        chl_stats = compare.compare(df, "chl_bing", "chla_argo")
        assert chl_stats["median_ratio"] == pytest.approx(1.5)

        strat = compare.add_strata(df)
        regions = dict(zip(strat["matchup_id"], strat["region"], strict=True))
        seasons = dict(zip(strat["matchup_id"], strat["season"], strict=True))
        assert regions == {"M1": "subtropics", "M2": "tropics"}
        assert seasons == {"M1": "DJF", "M2": "JJA"}


def test_add_oc_chl_from_granule():
    pytest.importorskip("ocpy")
    gran = make_granule()
    with Store.open(":memory:") as store:
        _seed(
            store,
            "M1",
            7902226,
            5,
            lat=20.0,
            lon=-50.0,
            time="2025-02-18T20:00:00",
            bbp_argo=1e-3,
            chla=0.1,
            bbp_bing=2e-3,
        )
        df = compare.gather_matchups(store)
        out = compare.add_oc_chl(df, store, opener=lambda s: gran)
        assert "chl_oc" in out and np.isfinite(out["chl_oc"].iloc[0])


# -- scene quick-look -------------------------------------------------------
def test_locate_float_pixel():
    ds = make_granule(center=(20.0, -50.0))
    lat = float(ds["latitude"].values[2, 2])
    lon = float(ds["longitude"].values[2, 2])
    assert scene.locate_float_pixel(ds, lat, lon) == (2, 2)


def test_scene_quicklook_file_and_budget(tmp_path):
    ds = make_granule(center=(20.0, -50.0), flagged=[(0, 0, "LAND")])
    lat = float(ds["latitude"].values[2, 2])
    lon = float(ds["longitude"].values[2, 2])
    out = scene.scene_quicklook(
        ds, lat, lon, pixels=[{"ix": 2, "iy": 2}], outfile=tmp_path / "scene.png"
    )
    assert out.exists() and out.stat().st_size < scene.SIZE_BUDGET


# -- population figures -----------------------------------------------------
def test_comparison_scatter_file_and_budget(tmp_path):
    import pandas as pd

    df = pd.DataFrame(
        {
            "bbp_bing": [2e-3, 4e-3, 6e-3],
            "bbp_argo": [1e-3, 2e-3, 3e-3],
            "latitude": [27.0, 4.0, -30.0],
            "longitude": [-46.0, -137.0, 10.0],
        }
    )
    out = population.comparison_scatter(
        df, "bbp_bing", "bbp_argo", outfile=tmp_path / "scatter.png"
    )
    assert out.exists() and out.stat().st_size < population.SIZE_BUDGET
    assert population.matchup_map(df, outfile=tmp_path / "map.png").exists()


# -- per-matchup fit figure (needs bing + its model data) -------------------
def test_fit_figure_smoke(tmp_path, monkeypatch):
    pytest.importorskip("bing")
    pytest.importorskip("emcee")
    from pab.fit import FitConfig, artifacts, run
    from pab.plotting import fit_fig

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    gran = make_granule(center=(20.0, -50.0))
    with Store.open(":memory:") as store:
        _seed(
            store,
            "M1",
            7902226,
            5,
            lat=20.0,
            lon=-50.0,
            time="2025-02-18T20:00:00",
            bbp_argo=1e-3,
            chla=0.1,
            bbp_bing=2e-3,
        )
        config = FitConfig(nsteps=600, nburn=150, analysis_burn=150)
        try:
            fit_id = run.fit_matchup(store, "M1", config=config, opener=lambda s: gran)
        except FileNotFoundError as exc:
            pytest.skip(f"BING aph-basis data unavailable: {exc}")
        out = fit_fig.fit_figure(store, fit_id, outfile=tmp_path / "fit.png")
        assert out.exists() and out.stat().st_size < fit_fig.SIZE_BUDGET
