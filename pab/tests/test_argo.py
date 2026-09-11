"""Stage 2 tests: BGC-Argo mixed-layer summary (``pab.argo``)."""

import numpy as np
import pytest
import xarray as xr

from pab.argo import fetch, mld, summary
from pab.db import Store


# -- MLD: known answer on a synthetic density profile -----------------------
def test_mld_known_answer():
    # SIG0 jumps past the 10 m value + 0.03 between 30 and 40 dbar.
    pres = np.array([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    sig0 = np.array([25.00, 25.00, 25.005, 25.01, 25.05, 25.10])
    assert mld.mixed_layer_depth(pres, sig0) == pytest.approx(40.0)


def test_mld_custom_threshold():
    pres = np.array([5.0, 10.0, 20.0, 30.0])
    sig0 = np.array([25.0, 25.0, 25.02, 25.2])
    # threshold 0.01 -> crosses at 20 dbar
    assert mld.mixed_layer_depth(pres, sig0, threshold=0.01) == pytest.approx(20.0)


def test_mld_unresolved_returns_nan():
    # Fully mixed column: never exceeds the threshold.
    pres = np.array([5.0, 10.0, 20.0, 30.0])
    sig0 = np.array([25.0, 25.0, 25.0, 25.0])
    assert np.isnan(mld.mixed_layer_depth(pres, sig0))


def test_mld_too_shallow_returns_nan():
    # Profile does not reach the 10 m reference depth.
    pres = np.array([1.0, 2.0, 3.0])
    sig0 = np.array([25.0, 25.1, 25.2])
    assert np.isnan(mld.mixed_layer_depth(pres, sig0))


def test_mld_handles_unsorted_and_nan():
    pres = np.array([40.0, np.nan, 10.0, 20.0, 5.0, 30.0])
    sig0 = np.array([25.05, 99.0, 25.00, 25.005, 25.00, 25.01])
    assert mld.mixed_layer_depth(pres, sig0) == pytest.approx(40.0)


def test_mld_from_ts_matches_density_path():
    # gsw is installed; derive SIG0 then compare to the direct path.
    pytest.importorskip("gsw")
    pres = np.linspace(0, 200, 41)
    psal = np.full_like(pres, 35.0)
    temp = np.where(pres < 50, 20.0, 12.0)  # thermocline near 50 m
    lon, lat = -30.0, 45.0
    sig0 = mld.density_sigma0(pres, psal, temp, lon, lat)
    direct = mld.mixed_layer_depth(pres, sig0)
    via_ts = mld.mixed_layer_depth_from_ts(pres, psal, temp, lon, lat)
    assert via_ts == pytest.approx(direct)
    assert np.isfinite(via_ts)


# -- de-spike ---------------------------------------------------------------
def test_despike_removes_injected_spike():
    base = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    spiked = base.copy()
    spiked[3] = 10.0  # bubble spike
    filtered = summary.despike(spiked)
    assert filtered[3] == pytest.approx(1.0)
    # untouched away from the spike
    assert filtered[0] == pytest.approx(1.0)
    assert filtered[-1] == pytest.approx(1.0)


def test_despike_preserves_step_edges():
    x = np.array([1.0, 1.0, 1.0, 5.0, 5.0, 5.0])
    out = summary.despike(x)
    # A real step (not a single-sample spike) survives the median filter.
    assert out[-1] == pytest.approx(5.0)


def test_moving_median_rejects_even_window():
    with pytest.raises(ValueError):
        summary.moving_median([1, 2, 3], window=2)


def test_moving_median_handles_scalar_profile():
    # a profile with a single BBP700/CHLA sample arrives 0-dimensional; slicing a
    # 0-d array used to raise IndexError and abort the whole ingest (pilot bug).
    out = summary.moving_median(3.0)
    assert out.shape == (1,) and out[0] == pytest.approx(3.0)


# -- mixed-layer average ----------------------------------------------------
def test_mixed_layer_mean_correctness():
    pres = np.array([5.0, 10.0, 20.0, 30.0])
    vals = np.array([2.0, 4.0, 6.0, 8.0])
    mean, std, n = summary.mixed_layer_mean(pres, vals, mld=15.0)
    assert n == 2
    assert mean == pytest.approx(3.0)  # mean of [2, 4]
    assert std == pytest.approx(1.0)


def test_mixed_layer_mean_nan_mld():
    pres = np.array([5.0, 10.0])
    vals = np.array([2.0, 4.0])
    mean, std, n = summary.mixed_layer_mean(pres, vals, mld=float("nan"))
    assert n == 0 and np.isnan(mean)


def test_mixed_layer_mean_qc_filter_drops_bad_flag():
    # chl_cdom_matchups.md R2: dropping Argo QC=4 ("bad") points before
    # averaging must change the result relative to the QC-blind call.
    pres = np.array([5.0, 10.0, 20.0, 30.0])
    vals = np.array([1.0, 1.2, 0.8, 100.0])  # last point is a QC=4 outlier
    qc = np.array([1.0, 2.0, 3.0, 4.0])

    raw_mean, _, raw_n = summary.mixed_layer_mean(pres, vals, mld=25.0)
    assert raw_n == 3  # 100.0 is excluded only because pres=30 > mld=25 here

    # Widen the MLD so the QC=4 point would otherwise be included.
    unfiltered_mean, _, unfiltered_n = summary.mixed_layer_mean(pres, vals, mld=35.0)
    assert unfiltered_n == 4
    assert unfiltered_mean == pytest.approx(np.mean(vals))

    filtered_mean, _, filtered_n = summary.mixed_layer_mean(
        pres, vals, mld=35.0, qc=qc, bad_qc=frozenset({4})
    )
    assert filtered_n == 3
    assert filtered_mean == pytest.approx(np.mean([1.0, 1.2, 0.8]))


def test_mixed_layer_mean_qc_none_is_a_no_op():
    # qc=None (the project's default) must reproduce the QC-blind result
    # exactly, even when bad_qc is non-empty — no QC screening happens unless
    # an actual qc array is supplied.
    pres = np.array([5.0, 10.0])
    vals = np.array([1.0, 2.0])
    mean, std, n = summary.mixed_layer_mean(pres, vals, mld=15.0, bad_qc=frozenset({4}))
    assert n == 2
    assert mean == pytest.approx(1.5)


def test_iqr_filter_drops_outlier():
    vals = np.array([1.0e-3] * 10 + [1.0])  # one gross outlier
    mask = summary.iqr_inlier_mask(vals)
    assert mask[:-1].all()
    assert not mask[-1]


# -- summarize_profile ------------------------------------------------------
def test_summarize_profile_end_to_end():
    pres = np.array([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    sig0 = np.array([25.00, 25.00, 25.005, 25.01, 25.05, 25.10])  # MLD = 40
    bbp = np.array([2.0e-3, 2.0e-3, 9.0e-2, 2.0e-3, 2.0e-3, 1.0e-3])  # spike@idx2
    chla = np.array([0.5, 0.5, 0.5, 0.5, 0.2, 0.1])
    out = summary.summarize_profile(
        pres, bbp700=bbp, chla=chla, sig0=sig0, despike_bbp=True, iqr_filter=False
    )
    assert out["mld"] == pytest.approx(40.0)
    assert out["mld_method"] == mld.MLD_METHOD
    # within MLD (pres <= 40): 5 samples; the spike is de-spiked to ~2e-3
    assert out["n_points"] == 5
    assert out["bbp700"] == pytest.approx(2.0e-3, rel=0.1)
    assert out["chla"] == pytest.approx(np.mean([0.5, 0.5, 0.5, 0.5, 0.2]))


def test_summarize_profile_averages_cdom_and_chla_adjusted():
    # Mirrors test_summarize_profile_end_to_end's CHLA check: cdom/chla_adjusted
    # get the same plain mixed-layer mean as chla (no despike/IQR, unlike bbp700).
    pres = np.array([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    sig0 = np.array([25.00, 25.00, 25.005, 25.01, 25.05, 25.10])  # MLD = 40
    cdom = np.array([1.0, 1.2, 0.8, 1.0, 2.0, 5.0])
    chla_adjusted = np.array([0.6, 0.6, 0.6, 0.6, 0.3, 0.1])
    out = summary.summarize_profile(pres, cdom=cdom, chla_adjusted=chla_adjusted, sig0=sig0)
    assert out["mld"] == pytest.approx(40.0)
    # within MLD (pres <= 40): first 5 samples
    assert out["cdom"] == pytest.approx(np.mean([1.0, 1.2, 0.8, 1.0, 2.0]))
    assert out["cdom_std"] == pytest.approx(np.std([1.0, 1.2, 0.8, 1.0, 2.0]))
    assert out["chla_adjusted"] == pytest.approx(np.mean([0.6, 0.6, 0.6, 0.6, 0.3]))


def test_summarize_profile_computes_qc_filtered_cdom():
    # chl_cdom_matchups.md R2: when cdom_qc is supplied alongside cdom, a
    # second, QC=4-screened mean is computed and reported, alongside the
    # original QC-blind cdom/cdom_std (an addition, not a replacement).
    pres = np.array([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    sig0 = np.array([25.00, 25.00, 25.005, 25.01, 25.05, 25.10])  # MLD = 40
    cdom = np.array([1.0, 1.2, 0.8, 1.0, 50.0, 5.0])  # idx4 is a QC=4 outlier
    cdom_qc = np.array([1.0, 2.0, 3.0, 1.0, 4.0, 1.0])
    out = summary.summarize_profile(pres, cdom=cdom, cdom_qc=cdom_qc, sig0=sig0)
    # QC-blind cdom is unchanged: mean over the first 5 in-MLD samples.
    assert out["cdom"] == pytest.approx(np.mean([1.0, 1.2, 0.8, 1.0, 50.0]))
    # QC-filtered drops the one QC=4 point (idx4, value 50.0) from the MLD.
    assert out["cdom_qc_filtered"] == pytest.approx(np.mean([1.0, 1.2, 0.8, 1.0]))
    assert out["cdom_n_qc4_dropped"] == 1


def test_summarize_profile_qc_filtered_cdom_absent_without_qc_array():
    # A valid cdom mean is still computed even when no cdom_qc is supplied;
    # the QC-filtered fields simply stay at their NaN/0 defaults rather than
    # raising or silently mirroring the QC-blind value. Reuses the known-good
    # MLD=40 fixture from test_summarize_profile_averages_cdom_and_chla_adjusted.
    pres = np.array([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    sig0 = np.array([25.00, 25.00, 25.005, 25.01, 25.05, 25.10])  # MLD = 40
    cdom = np.array([1.0, 1.2, 0.8, 1.0, 2.0, 5.0])
    out = summary.summarize_profile(pres, cdom=cdom, sig0=sig0)
    assert out["mld"] == pytest.approx(40.0)
    assert out["cdom"] == pytest.approx(np.mean([1.0, 1.2, 0.8, 1.0, 2.0]))
    assert np.isnan(out["cdom_qc_filtered"])
    assert out["cdom_n_qc4_dropped"] == 0


def test_summarize_profile_omits_cdom_and_chla_adjusted_when_absent():
    # Neither is measured on every float/profile -> must default to NaN, not
    # raise or silently omit the key (persist_summary's whitelist reads it).
    pres = np.array([5.0, 10.0, 20.0])
    out = summary.summarize_profile(pres, bbp700=np.full(3, 2e-3))
    assert np.isnan(out["cdom"]) and np.isnan(out["cdom_std"])
    assert np.isnan(out["chla_adjusted"])


def test_summarize_profile_requires_lonlat_for_ts():
    pres = np.array([5.0, 10.0, 20.0])
    with pytest.raises(ValueError):
        summary.summarize_profile(pres, psal=np.full(3, 35.0), temp=np.full(3, 20.0))


# -- persistence ------------------------------------------------------------
def test_summary_row_persisted():
    pres = np.array([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    sig0 = np.array([25.00, 25.00, 25.005, 25.01, 25.05, 25.10])
    bbp = np.array([2.0e-3, 2.0e-3, 2.0e-3, 2.0e-3, 2.0e-3, 1.0e-3])
    out = summary.summarize_profile(pres, bbp700=bbp, sig0=sig0)

    with Store.open(":memory:") as store:
        pid = summary.persist_summary(
            store,
            wmo=6903823,
            cycle=387,
            summary=out,
            latitude=45.0,
            longitude=-30.0,
            time="2024-05-01T00:00:00",
            data_mode="D",
            created="2026-06-20T00:00:00",
        )
        assert pid == 1
        rows = store.query("SELECT * FROM mld_summary WHERE profile_id = ?", (pid,))
        assert len(rows) == 1
        assert rows[0]["mld"] == pytest.approx(40.0)
        assert rows[0]["bbp700"] == pytest.approx(2.0e-3, rel=0.1)
        # float + profile rows created too
        assert store.count("floats") == 1
        assert store.count("profiles") == 1

        # idempotent: re-persist updates in place, no duplicate
        summary.persist_summary(
            store,
            wmo=6903823,
            cycle=387,
            summary=out,
            latitude=45.0,
            longitude=-30.0,
            created="2026-06-20T01:00:00",
        )
        assert store.count("profiles") == 1
        assert store.count("mld_summary") == 1


# -- fetch seam (no network) ------------------------------------------------
def test_build_fetcher_is_bgc():
    argopy = pytest.importorskip("argopy")
    f = fetch.build_fetcher()
    # A DataFetcher configured for BGC; constructing it does not hit the network.
    assert isinstance(f, argopy.DataFetcher)


def test_iter_profiles_extracts_dac_and_project_metadata():
    """PROJECT_NAME/DATA_CENTRE (and DATA_MODE) must reach the yielded meta.

    Regression test for the provenance bug found while planning the chl-a/CDOM
    deep dive: ``iter_profiles`` extracted these but ``pipeline.ingest()``
    never forwarded them to ``persist_summary``, so ``floats.project_name``/
    ``data_center`` were NULL for every float in the full production run. This
    test only exercises ``iter_profiles``'s own extraction (via a fake ``.argo``
    accessor standing in for argopy's ``point2profile`` transform, so no real
    argopy dependency is needed here); the pipeline-level round trip is covered
    separately in ``test_pipeline.py``.
    """

    class _FakeAccessor:
        def point2profile(self_inner):  # noqa: N805 - mimics argopy's accessor
            return prof

    class _FakeDataset:
        argo = _FakeAccessor()

    prof = xr.Dataset(
        {
            "PLATFORM_NUMBER": ("N_PROF", [1234567]),
            "CYCLE_NUMBER": ("N_PROF", [12]),
            "LATITUDE": ("N_PROF", [10.0]),
            "LONGITUDE": ("N_PROF", [-40.0]),
            "TIME": (
                "N_PROF",
                np.array(["2025-05-01T12:00:00"], dtype="datetime64[ns]"),
            ),
            "DATA_MODE": ("N_PROF", ["R"]),
            "PROJECT_NAME": ("N_PROF", ["Test Project  "]),
            "DATA_CENTRE": ("N_PROF", ["AO"]),
            "CHLA_DATA_MODE": ("N_PROF", ["A"]),
            "CDOM_DATA_MODE": ("N_PROF", ["R"]),
            "BBP700_DATA_MODE": ("N_PROF", ["D"]),
            "PRES": (("N_PROF", "N_LEVELS"), [[0.0, 10.0, 20.0]]),
            "CHLA": (("N_PROF", "N_LEVELS"), [[0.2, 0.2, 0.2]]),
            "CHLA_ADJUSTED": (("N_PROF", "N_LEVELS"), [[0.25, 0.25, 0.25]]),
            "CDOM": (("N_PROF", "N_LEVELS"), [[1.0, 1.0, 1.0]]),
            "CDOM_QC": (("N_PROF", "N_LEVELS"), [[1.0, 3.0, 4.0]]),
        }
    )

    meta, variables = next(fetch.iter_profiles(_FakeDataset()))

    assert meta["wmo"] == 1234567
    assert meta["cycle"] == 12
    assert meta["data_mode"] == "R"
    assert meta["project_name"] == "Test Project"  # stripped of Argo's char padding
    assert meta["data_center"] == "AO"
    # per-parameter modes, distinct from the (unpopulated on real fetches)
    # whole-profile data_mode above
    assert meta["chla_data_mode"] == "A"
    # R2: CDOM_QC extracted alongside CDOM, for the QC-filtered mixed-layer mean
    assert list(variables["CDOM_QC"]) == [1.0, 3.0, 4.0]
    assert meta["cdom_data_mode"] == "R"
    assert meta["bbp700_data_mode"] == "D"
    assert "PRES" in variables and "CHLA" in variables
    assert "CDOM" in variables and "CHLA_ADJUSTED" in variables


# -- CDOM sensor-model fetch (R6) --------------------------------------------
def test_fetch_cdom_sensor_model_finds_cdom_row(tmp_path):
    xr = pytest.importorskip("xarray")
    meta_path = tmp_path / "meta.nc"
    xr.Dataset(
        {
            "SENSOR": ("N_SENSOR", ["CTD_PRES", "FLUOROMETER_CDOM"]),
            "SENSOR_MODEL": ("N_SENSOR", ["DRUCK_2900PSIA", "MCOMS_FLBBCD"]),
        }
    ).to_netcdf(meta_path)

    calls = []

    def _fake_downloader(url):
        calls.append(url)
        return meta_path.read_bytes()

    model = fetch.fetch_cdom_sensor_model(1901614, "AO", downloader=_fake_downloader)
    assert model == "MCOMS_FLBBCD"
    assert calls == ["https://data-argo.ifremer.fr/dac/aoml/1901614/1901614_meta.nc"]


def test_fetch_cdom_sensor_model_no_cdom_sensor(tmp_path):
    xr = pytest.importorskip("xarray")
    meta_path = tmp_path / "meta.nc"
    xr.Dataset(
        {
            "SENSOR": ("N_SENSOR", ["CTD_PRES"]),
            "SENSOR_MODEL": ("N_SENSOR", ["DRUCK_2900PSIA"]),
        }
    ).to_netcdf(meta_path)
    model = fetch.fetch_cdom_sensor_model(
        1234567, "IF", downloader=lambda url: meta_path.read_bytes()
    )
    assert model is None


def test_fetch_cdom_sensor_model_unknown_dac_returns_none():
    def _fail(url):
        raise AssertionError("must not fetch when the DAC code has no folder mapping")

    assert fetch.fetch_cdom_sensor_model(1234567, "ZZ", downloader=_fail) is None
    assert fetch.fetch_cdom_sensor_model(1234567, None, downloader=_fail) is None


def test_fetch_cdom_sensor_model_download_failure_returns_none():
    def _boom(url):
        raise OSError("network down")

    assert fetch.fetch_cdom_sensor_model(1901614, "AO", downloader=_boom) is None


def test_persist_cdom_sensor_model_does_not_clobber_other_float_fields():
    with Store.open(":memory:") as store:
        store.upsert(
            "floats", {"wmo": 1901614, "project_name": "Solo", "data_center": "AO"}
        )
        summary.persist_cdom_sensor_model(store, wmo=1901614, sensor_model="MCOMS_FLBBCD")
        row = store.query("SELECT * FROM floats WHERE wmo = ?", (1901614,))[0]
        assert row["cdom_sensor_model"] == "MCOMS_FLBBCD"
        assert row["project_name"] == "Solo"  # untouched by the targeted upsert
        assert row["data_center"] == "AO"


# -- Q&A plot ---------------------------------------------------------------
def test_qa_plot_produced(tmp_path):
    pytest.importorskip("matplotlib")
    from pab.argo import qa

    pres = np.array([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    bbp = np.array([2.0e-3, 2.0e-3, 9.0e-2, 2.0e-3, 2.0e-3, 1.0e-3])
    chla = np.array([0.5, 0.5, 0.5, 0.5, 0.2, 0.1])
    out = qa.save_profile_qa(
        tmp_path / "qa.png",
        pres,
        bbp700=bbp,
        chla=chla,
        mld=40.0,
        title="WMO 6903823 / cycle 387",
    )
    assert out.exists() and out.stat().st_size > 0


def test_qa_uses_headless_backend():
    # regression: ingest renders Q&A figures alongside argopy worker threads, where
    # an interactive (Tk) backend aborts the process. The backend must be Agg.
    pytest.importorskip("matplotlib")
    import os

    import matplotlib

    from pab.argo import qa  # noqa: F401 — importing forces matplotlib.use("Agg")

    assert os.environ.get("MPLBACKEND") == "Agg"
    assert matplotlib.get_backend().lower() == "agg"


def test_mixed_layer_mean_handles_length_mismatch():
    """A variable not aligned with the pressure axis must not kill the profile.

    Real argopy returns did this in the 1000-profile run: one BBP700 value
    against 555 pressures. numpy broadcasts the finite-mask to 555 and then
    raises IndexError on the indexing, which failed 14 profiles outright.
    """
    pres = np.linspace(0.0, 100.0, 555)
    mean, std, n = summary.mixed_layer_mean(pres, np.array([2e-3]), 30.0)
    assert np.isnan(mean) and np.isnan(std) and n == 0
    # the aligned case is unaffected
    mean, std, n = summary.mixed_layer_mean(pres, np.full(555, 2e-3), 30.0)
    assert mean == pytest.approx(2e-3) and n > 0


def test_summarize_profile_survives_a_mismatched_variable():
    pytest.importorskip("gsw")
    pres = np.linspace(0.0, 200.0, 100)
    out = summary.summarize_profile(
        pres,
        bbp700=np.array([2e-3]),          # mismatched -> skipped
        chla=np.full(100, 0.2),           # aligned -> still summarized
        psal=np.full(100, 35.0),
        temp=np.linspace(20.0, 10.0, 100),
        lon=-40.0,
        lat=10.0,
    )
    assert np.isnan(out["bbp700"])
    assert out["chla"] == pytest.approx(0.2)
    assert np.isfinite(out["mld"])
