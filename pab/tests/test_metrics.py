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


def test_gather_matchups_filters_by_model_pair():
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
        )
        # a SECOND model-pair fit on the same matchup must not duplicate the row
        store.upsert(
            "fits",
            {
                "fit_id": "M1_2_2_Cst",
                "matchup_id": "M1",
                "algorithm": "BING",
                "model_pair": "Cst",
                "chisq": 2.0,
                "pab_version": "0",
            },
        )
        store.upsert(
            "fit_results",
            {
                "fit_id": "M1_2_2_Cst",
                "quantity": "BING_Cst_bbp700",
                "value": 9e-3,
                "value_lo": 8e-3,
                "value_hi": 1e-2,
                "unit": "m^-1",
            },
        )
        df = compare.gather_matchups(store)  # default ExpBPow
        assert len(df) == 1  # not 2 — the Cst fit is filtered out
        assert df["bbp_bing"].iloc[0] == pytest.approx(2e-3)  # ExpBPow, not Cst's 9e-3


def test_gather_nasa_giop_joins_bing_and_nasa_fits():
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
        )
        # a matchup with only a BING fit (no NASA-GIOP ingest yet) must not appear
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
        )
        store.upsert(
            "fits",
            {
                "fit_id": "M1_2_2_NASA_GIOP",
                "matchup_id": "M1",
                "algorithm": "NASA_GIOP",
                "pab_version": "1.1",
            },
        )
        store.upsert_many(
            "fit_results",
            [
                {
                    "fit_id": "M1_2_2_NASA_GIOP",
                    "quantity": "NASA_GIOP_bbp_442",
                    "value": 3e-3,
                    "value_lo": 2.5e-3,
                    "value_hi": 3.5e-3,
                    "unit": "m^-1",
                },
                {
                    "fit_id": "M1_2_2_NASA_GIOP",
                    "quantity": "NASA_GIOP_adg_442",
                    "value": 0.03,
                    "value_lo": None,
                    "value_hi": None,
                    "unit": "m^-1",
                },
            ],
        )
        df = compare.gather_nasa_giop(store)
        assert len(df) == 1  # only M1 has both a BING and a NASA-GIOP fit
        row = df.iloc[0]
        assert row["matchup_id"] == "M1"
        assert row["bbp_bing"] == pytest.approx(2e-3)
        assert row["bbp_442_nasa"] == pytest.approx(3e-3)
        assert row["adg_442_nasa"] == pytest.approx(0.03)
        assert row["aph_442_nasa"] is None or np.isnan(row["aph_442_nasa"])
        # no NASA_GIOP_bbp_s row -> the 700 nm columns are NaN, not a guess
        assert np.isnan(row["bbp_s_nasa"])
        for c in ("bbp_700_nasa", "bbp_700_nasa_lo", "bbp_700_nasa_hi"):
            assert c in df.columns and np.isnan(row[c])


def test_giop_bbp_to_700_helper_and_ceiling_fraction():
    factor = (442.0 / 700.0) ** 1.5
    assert compare.giop_bbp_to_700(3e-3, 1.5) == pytest.approx(3e-3 * factor)
    # a null slope gives NaN (per-pixel slope only, no default)
    assert np.isnan(compare.giop_bbp_to_700(3e-3, None))
    assert np.isnan(compare.giop_bbp_to_700(None, 1.5))
    out = compare.giop_bbp_to_700([1e-3, 2e-3], [0.0, np.nan])
    assert out[0] == pytest.approx(1e-3) and np.isnan(out[1])
    # the formula text is built from the same constants as the helper
    assert compare.GIOP_BBP_SHIFT_FORMULA == "b_bp(700) = b_bp(442) × (442/700)^bbp_s"
    # ceiling fraction: 1.99 counts as pinned at 2.0, NaN is ignored
    assert compare.giop_slope_ceiling_fraction([2.0, 1.99, 1.5, 0.3, np.nan]) == (
        pytest.approx(0.5)
    )
    assert np.isnan(compare.giop_slope_ceiling_fraction([np.nan]))


def test_gather_nasa_giop_shifts_bbp_to_700():
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
        )
        store.upsert(
            "fits",
            {
                "fit_id": "M1_2_2_NASA_GIOP",
                "matchup_id": "M1",
                "algorithm": "NASA_GIOP",
                "pab_version": "1.1",
            },
        )
        store.upsert_many(
            "fit_results",
            [
                {
                    "fit_id": "M1_2_2_NASA_GIOP",
                    "quantity": "NASA_GIOP_bbp_442",
                    "value": 3e-3,
                    "value_lo": 2.5e-3,
                    "value_hi": 3.5e-3,
                    "unit": "m^-1",
                },
                {
                    "fit_id": "M1_2_2_NASA_GIOP",
                    "quantity": "NASA_GIOP_bbp_s",
                    "value": 1.5,
                    "value_lo": None,
                    "value_hi": None,
                    "unit": "",
                },
            ],
        )
        df = compare.gather_nasa_giop(store)
        assert len(df) == 1
        row = df.iloc[0]
        factor = (442.0 / 700.0) ** 1.5
        assert row["bbp_s_nasa"] == pytest.approx(1.5)
        # value and both bounds scale by the same per-pixel factor
        assert row["bbp_700_nasa"] == pytest.approx(3e-3 * factor)
        assert row["bbp_700_nasa_lo"] == pytest.approx(2.5e-3 * factor)
        assert row["bbp_700_nasa_hi"] == pytest.approx(3.5e-3 * factor)
        # the 442 nm columns are kept as stored
        assert row["bbp_442_nasa"] == pytest.approx(3e-3)
        assert row["bbp_442_nasa_lo"] == pytest.approx(2.5e-3)


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


def test_false_color_rgba():
    ds = make_granule(center=(20.0, -50.0), flagged=[(0, 0, "LAND")])
    rgba, used = scene.false_color_rgba(ds)
    assert rgba.shape == (5, 5, 4)  # (x, y, RGBA)
    assert np.all((rgba >= 0) & (rgba <= 1))  # normalised channels
    assert len(used) == 3  # three band wavelengths chosen (R, G, B)
    # flagged pixel rendered as the grey flag colour
    assert tuple(rgba[0, 0]) == scene._FLAG_RGBA


def test_scene_quicklook_rgb_and_band_budget(tmp_path):
    ds = make_granule(center=(20.0, -50.0), flagged=[(0, 0, "LAND")])
    lat = float(ds["latitude"].values[2, 2])
    lon = float(ds["longitude"].values[2, 2])
    # default is the false-color RGB composite
    rgb = scene.scene_quicklook(
        ds, lat, lon, pixels=[{"ix": 2, "iy": 2}], outfile=tmp_path / "rgb.png"
    )
    assert rgb.exists() and rgb.stat().st_size < scene.SIZE_BUDGET
    # single-band mode still works
    band = scene.scene_quicklook(
        ds, lat, lon, mode="band", outfile=tmp_path / "band.png"
    )
    assert band.exists() and band.stat().st_size < scene.SIZE_BUDGET


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
    assert population.matchup_map(
        df, outfile=tmp_path / "map.png", projection=None
    ).exists()


def _dense_frame(n=3000, seed=0):
    """A sat/float population dense enough to fill histogram cells.

    Log-**uniform** over one decade, deliberately: the 99 % clip pads the
    percentile range by × 0.7 / × 1.4, which covers a bounded distribution
    entirely, so nothing is off-scale unless a test puts it there. (A
    log-normal has tails beyond the clip and would add off-scale points of
    its own.)
    """
    import pandas as pd

    rng = np.random.default_rng(seed)
    insitu = 10 ** rng.uniform(-3.5, -2.5, n)
    sat = insitu * 10 ** rng.uniform(-0.1, 0.3, n)
    return pd.DataFrame({"bbp_bing": sat, "bbp_argo": insitu})


def _mesh_and_dots(fig):
    """The (QuadMesh, dot Line2D) drawn by ``density_scatter``, or ``None``s."""
    from matplotlib.collections import QuadMesh

    ax = fig.axes[0]
    mesh = next((c for c in ax.collections if isinstance(c, QuadMesh)), None)
    dots = next((ln for ln in ax.lines if ln.get_marker() == "o"), None)
    return mesh, dots


def test_density_scatter_file_and_budget(tmp_path):
    df = _dense_frame()
    out = population.density_scatter(
        df, "bbp_bing", "bbp_argo", outfile=tmp_path / "density.png"
    )
    assert out.exists() and out.stat().st_size < population.SIZE_BUDGET
    # a dense population draws filled cells AND leaves some sparse-cell dots
    import matplotlib.pyplot as plt

    fig = population.density_scatter(df, "bbp_bing", "bbp_argo", cmap="Greens")
    mesh, dots = _mesh_and_dots(fig)
    assert mesh is not None and dots is not None
    assert fig.axes[0].get_xscale() == "log" and fig.axes[0].get_yscale() == "log"
    assert any(a.get_ylabel() == "matchups per cell" for a in fig.axes[1:])
    plt.close(fig)


def test_density_scatter_small_frame_is_all_dots():
    import matplotlib.pyplot as plt
    import pandas as pd

    # 20 distinct points over 50 x 50 cells: no cell reaches min_count=5
    insitu = np.logspace(-4, -2, 20)
    df = pd.DataFrame({"bbp_bing": insitu * 1.5, "bbp_argo": insitu})
    fig = population.density_scatter(df, "bbp_bing", "bbp_argo")
    mesh, dots = _mesh_and_dots(fig)
    assert mesh is None and dots is not None
    assert len(dots.get_xdata()) == 20
    assert fig.axes[0].get_title().startswith("n=20")
    assert "off-scale" not in fig.axes[0].get_title()
    plt.close(fig)


def test_density_scatter_ignores_nan_and_nonpositive():
    import matplotlib.pyplot as plt

    df = _dense_frame(n=500)
    df.loc[0, "bbp_bing"] = np.nan
    df.loc[1, "bbp_argo"] = -1.0
    df.loc[2, "bbp_bing"] = 0.0
    fig = population.density_scatter(df, "bbp_bing", "bbp_argo")
    stats = compare.log_comparison(df["bbp_bing"], df["bbp_argo"])
    assert stats["n"] == 497
    assert fig.axes[0].get_title().startswith(f"n={stats['n']} ")
    plt.close(fig)


def test_density_scatter_counts_offscale_but_keeps_them_in_stats():
    import matplotlib.pyplot as plt

    df = _dense_frame(n=1000)
    df.loc[[0, 1, 2], "bbp_bing"] = 1e4  # three non-physical runaways
    fig = population.density_scatter(df, "bbp_bing", "bbp_argo")
    title = fig.axes[0].get_title()
    stats = compare.log_comparison(df["bbp_bing"], df["bbp_argo"])
    assert "[3 off-scale]" in title
    assert title.startswith(f"n={stats['n']} ")  # the runaways stay in n
    assert stats["n"] == 1000
    assert population.offscale_count(df, "bbp_bing", "bbp_argo") == 3
    # the runaways no longer set the axes
    assert fig.axes[0].get_ylim()[1] < 1.0
    plt.close(fig)
    # without a clip nothing is off-scale (and the title says nothing)
    fig = population.density_scatter(df, "bbp_bing", "bbp_argo", clip_percentile=None)
    assert "off-scale" not in fig.axes[0].get_title()
    assert population.offscale_count(df, "bbp_bing", "bbp_argo", clip_percentile=None) == 0
    plt.close(fig)


# -- maps (projection=None: plain axes, no cartopy, no network) -------------
def _map_frame(n=2000, seed=0, runaways=3):
    """Matchups spread over the oceans with a log-normal sat/float ratio
    (σ = 0.2 dex) and ``runaways`` satellite values at 1e4 m⁻¹."""
    import pandas as pd

    rng = np.random.default_rng(seed)
    insitu = 10 ** rng.uniform(-3.5, -2.5, n)
    sat = insitu * 10 ** rng.normal(0.05, 0.2, n)
    sat[:runaways] = 1e4
    return pd.DataFrame(
        {
            "bbp_bing": sat,
            "bbp_argo": insitu,
            "latitude": rng.uniform(-65, 65, n),
            "longitude": rng.uniform(-180, 180, n),
        }
    )


def test_matchup_map_plain_axes_file_and_budget(tmp_path):
    df = _map_frame()
    out = population.matchup_map(
        df, outfile=tmp_path / "matchup_map.png", projection=None
    )
    assert out.exists() and out.stat().st_size < population.MAP_SIZE_BUDGET
    import matplotlib.pyplot as plt

    fig = population.matchup_map(df, projection=None)
    ax = fig.axes[0]
    assert type(ax).__name__ == "Axes"  # not a cartopy GeoAxes
    assert ax.get_xlim() == (-180.0, 180.0) and ax.get_ylim() == (-90.0, 90.0)
    assert "2,000 matchups" in ax.get_title()
    assert "colour clipped at ±0.5 dex" in ax.get_title()
    assert any("log10(satellite / float b_bp)" in a.get_ylabel() for a in fig.axes[1:])
    plt.close(fig)


def test_maps_clip_at_fixed_symmetric_vmax_and_count_the_saturated():
    import matplotlib.pyplot as plt

    # Q&A/v2 Edits 5 = B: a fixed ±0.5 dex, not a percentile of the data
    vmax = population.LOG_RATIO_VMAX
    assert vmax == 0.5
    df = _map_frame()
    lr = population.log_ratio(df, "bbp_bing", "bbp_argo")
    assert np.isfinite(lr).all()
    expected = int((np.abs(lr) >= 0.5).sum())
    # the three 1e4 runaways (log-ratio ~ +7) are among the saturated, plus
    # the ~1.5 % tail of a σ = 0.2 dex distribution -- never the majority
    assert 3 <= expected < 100
    assert population.saturated_count(lr) == expected
    assert population.log_ratio_saturated(df, "bbp_bing", "bbp_argo") == (expected, 2000)
    # NaN ratios are neither saturated nor counted
    part = df.copy()
    part.loc[part.index[-10:], "bbp_argo"] = np.nan
    sat, n = population.log_ratio_saturated(part, "bbp_bing", "bbp_argo")
    assert n == 1990 and sat <= expected
    # both maps colour on exactly [-0.5, 0.5] by default and say so, with the
    # count of what the clip saturates
    fig = population.matchup_map(df, projection=None)
    norm = fig.axes[0].collections[-1].norm
    assert (norm.vmin, norm.vmax) == (-vmax, vmax)
    title = fig.axes[0].get_title()
    assert f"±0.5 dex ({expected} ({100 * expected / 2000:.1f} %) at or beyond)" in title
    plt.close(fig)
    fig = population.healpix_map(df, projection=None)
    norm = fig.axes[0].collections[-1].norm
    assert (norm.vmin, norm.vmax) == (-vmax, vmax)
    cells = population.healpix_medians(df, "bbp_bing", "bbp_argo")
    drawn = cells[cells["n"] >= population.HEALPIX_MIN_COUNT]
    sat_cells = int((np.abs(drawn["median_log_ratio"]) >= 0.5).sum())
    assert sat_cells < len(drawn) // 10  # the medians sit well inside the clip
    assert f"colour clipped at ±0.5 dex ({sat_cells} cells saturated)" in fig.axes[0].get_title()
    plt.close(fig)
    # a cell whose median is pushed past the clip is counted as saturated
    far = df.copy()
    far.loc[far.index[:200], "bbp_bing"] = far["bbp_argo"][:200] * 10 ** -0.8
    far.loc[far.index[:200], ["latitude", "longitude"]] = [[10.0, 10.0]] * 200
    fig = population.healpix_map(far, projection=None)
    far_cells = population.healpix_medians(far, "bbp_bing", "bbp_argo")
    far_drawn = far_cells[far_cells["n"] >= population.HEALPIX_MIN_COUNT]
    far_sat = population.saturated_count(far_drawn["median_log_ratio"])
    assert far_sat >= 1
    noun = "cell" if far_sat == 1 else "cells"
    assert f"({far_sat} {noun} saturated)" in fig.axes[0].get_title()
    plt.close(fig)
    # a caller may still pass its own limit
    fig = population.matchup_map(df, vmax=1.0, projection=None)
    norm = fig.axes[0].collections[-1].norm
    assert (norm.vmin, norm.vmax) == (-1.0, 1.0)
    plt.close(fig)
    # an all-NaN frame: nothing saturated, nothing counted, maps still draw
    empty = df.assign(bbp_argo=np.nan)
    assert population.log_ratio_saturated(empty, "bbp_bing", "bbp_argo") == (0, 0)
    fig = population.matchup_map(empty, projection=None)
    assert "0 matchups; colour clipped at ±0.5 dex (0 at or beyond)" in fig.axes[0].get_title()
    plt.close(fig)


def test_healpix_map_drops_thin_cells(tmp_path):
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.collections import PolyCollection

    rng = np.random.default_rng(3)
    # 40 matchups in one ~7° cell (jitter 0.1°), 2 in another, far away
    lat = np.r_[10.0 + rng.uniform(-0.1, 0.1, 40), -40.0, -40.05]
    lon = np.r_[10.0 + rng.uniform(-0.1, 0.1, 40), -150.0, -150.05]
    insitu = np.full(42, 1e-3)
    df = pd.DataFrame(
        {
            "bbp_bing": insitu * 10 ** np.r_[np.full(40, 0.1), -0.3, -0.3],
            "bbp_argo": insitu,
            "latitude": lat,
            "longitude": lon,
        }
    )
    cells = population.healpix_medians(df, "bbp_bing", "bbp_argo")
    assert sorted(cells["n"]) == [2, 40]
    assert cells.loc[cells["n"] == 40, "median_log_ratio"].iloc[0] == pytest.approx(0.1)
    out = population.healpix_map(
        df, outfile=tmp_path / "healpix_map.png", projection=None
    )
    assert out.exists() and out.stat().st_size < population.MAP_SIZE_BUDGET
    fig = population.healpix_map(df, projection=None)
    ax = fig.axes[0]
    coll = next(c for c in ax.collections if isinstance(c, PolyCollection))
    assert len(coll.get_paths()) == 1  # only the 40-matchup cell is drawn
    assert "1 HEALPix cells" in ax.get_title()
    assert "holding 40 matchups" in ax.get_title()
    assert "1 sparser cells not drawn" in ax.get_title()
    plt.close(fig)
    # a lower threshold draws both
    fig = population.healpix_map(df, min_count=2, projection=None)
    coll = next(c for c in fig.axes[0].collections if isinstance(c, PolyCollection))
    assert len(coll.get_paths()) == 2
    plt.close(fig)


def test_healpix_cell_outlines_at_the_dateline():
    import healpy

    from pab.report.aggregate import nside_for_cell_size

    nside = nside_for_cell_size(5.0)
    # every cell's pieces are compact: nothing spans more than half the globe,
    # nothing is degenerate (a zero-width piece projects as the whole globe)
    straddlers = []
    for p in range(healpy.nside2npix(nside)):
        pieces, split = population._dateline_pieces(*population._cell_outline(nside, p))
        assert len(pieces) == (2 if split else 1)
        if split:
            straddlers.append(pieces)
        for lon, lat in pieces:
            assert -180.0 <= lon.min() and lon.max() <= 180.0
            assert 0.5 < lon.max() - lon.min() <= 180.0
            assert lat.max() - lat.min() > 0.5
    # the cells that straddle 180° (at nside 8 the equatorial diamonds only
    # *touch* it; the rings beside them cross it) are split into a western
    # piece ending at 180° and an eastern piece starting at -180°
    assert straddlers
    for west, east in straddlers:
        assert west[0].max() == pytest.approx(180.0) and west[0].min() < 179.0
        assert east[0].min() == pytest.approx(-180.0) and east[0].max() > -179.0
    # the pole vertex takes its neighbours' longitude, not 0
    lon, lat = population._cell_outline(nside, 1)  # pole cell over 90-180° E
    assert 90.0 <= lon[np.abs(lat) > 89.999][0] <= 180.0


def test_matchup_map_without_cartopy_warns_and_uses_plain_axes(monkeypatch, caplog):
    import logging
    import sys

    import matplotlib.pyplot as plt

    monkeypatch.setitem(sys.modules, "cartopy", None)  # `import cartopy` fails
    with caplog.at_level(logging.WARNING, logger="pab.plotting"):
        fig = population.matchup_map(_map_frame(200), projection="robinson")
    assert "cartopy is not importable" in caplog.text
    assert type(fig.axes[0]).__name__ == "Axes"
    plt.close(fig)


def test_matchup_map_without_natural_earth_warns_and_keeps_robinson(
    monkeypatch, caplog
):
    pytest.importorskip("cartopy")
    import logging

    import matplotlib.pyplot as plt
    from cartopy.io import shapereader

    def _offline(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(shapereader, "natural_earth", _offline)
    with caplog.at_level(logging.WARNING, logger="pab.plotting"):
        fig = population.healpix_map(_map_frame(200), projection="robinson")
    assert "Natural Earth coastlines unavailable" in caplog.text
    assert type(fig.axes[0]).__name__ == "GeoAxes"
    plt.close(fig)


def _natural_earth_cached() -> bool:
    try:
        import cartopy
    except ImportError:
        return False
    from pathlib import Path

    root = Path(cartopy.config["data_dir"]) / "shapefiles" / "natural_earth" / "physical"
    return all((root / f"ne_110m_{n}.shp").is_file() for n in ("land", "coastline"))


@pytest.mark.skipif(
    not _natural_earth_cached(), reason="cartopy + cached Natural Earth needed (no download)"
)
def test_maps_on_robinson_axes_with_cached_coastlines(tmp_path):
    # the real path the report takes; only when the shapefiles are already
    # cached so the suite never downloads
    import matplotlib.pyplot as plt

    df = _map_frame()
    for fn, name in ((population.matchup_map, "dots"), (population.healpix_map, "cells")):
        out = fn(df, outfile=tmp_path / f"{name}.png", projection="robinson")
        assert out.exists() and out.stat().st_size < population.MAP_SIZE_BUDGET
        fig = fn(df, projection="robinson")
        assert type(fig.axes[0]).__name__ == "GeoAxes"
        plt.close(fig)


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
        # 1.0 config: the figure path reconstructs with Gordon until the
        # backend dispatch lands (Prompt 3 Task 4).
        config = FitConfig.v1(nsteps=600, nburn=150, analysis_burn=150)
        try:
            fit_id = run.fit_matchup(store, "M1", config=config, opener=lambda s: gran)
        except FileNotFoundError as exc:
            pytest.skip(f"BING aph-basis data unavailable: {exc}")
        out = fit_fig.fit_figure(store, fit_id, outfile=tmp_path / "fit.png")
        assert out.exists() and out.stat().st_size < fit_fig.SIZE_BUDGET
