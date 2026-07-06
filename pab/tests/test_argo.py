"""Stage 2 tests: BGC-Argo mixed-layer summary (``pab.argo``)."""

import numpy as np
import pytest

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
