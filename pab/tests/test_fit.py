"""Stage 5 tests: the BING fitting wrapper (``pab.fit``)."""

import numpy as np
import pytest

from pab.argo.summary import persist_summary
from pab.db import Store
from pab.fit import FitConfig, artifacts, run


# -- pure helpers (no bing) -------------------------------------------------
def test_make_fit_id():
    assert (
        run.make_fit_id("7902226_5_G1", 3, 4, "ExpBPow") == "7902226_5_G1_3_4_ExpBPow"
    )


def test_prepare_spectrum_window_and_variance():
    wave = np.array([380.0, 400.0, 500.0, 600.0, 700.0, 720.0])
    rrs = np.array([9.0, 0.01, 0.008, np.nan, 0.002, 9.0])
    unc = np.array([1.0, 0.001, 0.0008, 0.0, 0.0002, 1.0])
    w, r, var = run.prepare_spectrum(wave, rrs, unc, config=FitConfig())
    # 380/720 out of window; 600 is NaN -> dropped
    assert w.tolist() == [400.0, 500.0, 700.0]
    assert r.tolist() == [0.01, 0.008, 0.002]
    # finite, positive uncertainties -> var = unc**2 (the 0.0 at 600 is gone)
    assert np.allclose(var, np.array([0.001, 0.0008, 0.0002]) ** 2)


def test_prepare_spectrum_noise_floor_without_unc():
    wave = np.array([450.0, 550.0])
    rrs = np.array([0.01, 0.005])
    _, _, var = run.prepare_spectrum(wave, rrs, None)
    assert np.allclose(var, (0.02 * rrs) ** 2)


def test_prepare_spectrum_empty_window_raises():
    with pytest.raises(ValueError, match="within the fit window"):
        run.prepare_spectrum(np.array([300.0, 800.0]), np.array([0.01, 0.01]), None)


def test_finite_or_none_guards_nan_chla():
    assert run.finite_or_none(0.1) == 0.1
    assert run.finite_or_none(None) is None
    assert run.finite_or_none(np.nan) is None  # the NaN-chla guard
    assert run.finite_or_none(np.inf) is None


# -- persistence (no bing) --------------------------------------------------
def _seed_matchup(store):
    """floats→profiles→mld_summary→granule→matchup→pixel; return (matchup_id, pixel_id)."""
    pid = persist_summary(
        store,
        wmo=7902226,
        cycle=5,
        summary={"mld": 30.0, "mld_method": "x", "chla": 0.12, "n_points": 6},
        latitude=20.0,
        longitude=-50.0,
        time="2025-05-01T12:00:00",
    )
    store.upsert("granules", {"granule_id": "G1", "data_url": "s3://b/G1.nc"})
    store.upsert(
        "matchups",
        {
            "matchup_id": "7902226_5_G1",
            "profile_id": pid,
            "granule_id": "G1",
            "distance_km": 0.0,
            "dtime_hours": 0.5,
            "n_spectra": 1,
        },
    )
    store.upsert(
        "matchup_pixels",
        {"matchup_id": "7902226_5_G1", "ix": 2, "iy": 2, "rank": 1, "flagged": 0},
    )
    pixel_id = store.query(
        "SELECT pixel_id FROM matchup_pixels WHERE matchup_id = '7902226_5_G1'"
    )[0]["pixel_id"]
    return "7902226_5_G1", pixel_id


def _fake_result():
    return run.FitSpectrumResult(
        chains=np.zeros((4, 16, 5), dtype=float),
        wave=np.array([440.0, 550.0, 700.0]),
        Rrs=np.array([0.01, 0.005, 0.001]),
        varRrs=np.array([1e-8, 1e-8, 1e-8]),
        param_names=["Adg", "Sdg", "Aph", "Bnw", "beta"],
        quantities=[
            {
                "quantity": "bbp700",
                "value": 3.4e-3,
                "value_lo": 3.2e-3,
                "value_hi": 3.6e-3,
                "unit": "m^-1",
            },
            {
                "quantity": "beta",
                "value": 1.0,
                "value_lo": 0.8,
                "value_hi": 1.2,
                "unit": "",
            },
        ],
        anw_model="ExpBricaud",
        bbnw_model="Pow",
        nwalkers=16,
        chisq=0.9,
        aic=12.0,
        bic=15.0,
        accept_frac=0.3,
        success=True,
        Chl=0.12,
    )


def test_persist_fit_writes_links_quantities_and_is_idempotent():
    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        artifacts.persist_fit(
            store,
            fit_id="F1",
            matchup_id=matchup_id,
            pixel_id=pixel_id,
            result=_fake_result(),
            config=FitConfig(),
            chains_path="/tmp/F1.npz",
        )
        fit = store.query("SELECT * FROM fits")[0]
        assert fit["matchup_id"] == matchup_id and fit["pixel_id"] == pixel_id
        assert fit["algorithm"] == "BING" and fit["model_pair"] == "ExpBPow"
        assert fit["anw_model"] == "ExpBricaud" and fit["bbnw_model"] == "Pow"
        assert fit["pab_version"] and fit["created"] and fit["pkg_versions"]
        assert fit["chains_path"] == "/tmp/F1.npz"

        qs = store.query("SELECT quantity, value FROM fit_results ORDER BY quantity")
        names = [q["quantity"] for q in qs]
        assert names == ["BING_ExpBPow_bbp700", "BING_ExpBPow_beta"]

        # idempotent re-run: one fit row, quantities replaced (not duplicated)
        artifacts.persist_fit(
            store,
            fit_id="F1",
            matchup_id=matchup_id,
            pixel_id=pixel_id,
            result=_fake_result(),
            config=FitConfig(),
            chains_path="/tmp/F1.npz",
        )
        assert store.count("fits") == 1
        assert store.count("fit_results") == 2


def test_build_fits_records_failed_without_aborting():
    def _boom(_src):
        raise RuntimeError("granule unavailable")

    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        out = run.build_fits(store, opener=_boom)
        fit_id = run.make_fit_id(matchup_id, 2, 2, "ExpBPow")
        assert out["written"] == [] and out["skipped"] == []
        assert out["failed"] == [fit_id]
        assert store.count("fits") == 0  # the failed fit wrote nothing


def test_save_load_chains_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    res = _fake_result()
    path = artifacts.save_chains("F9", res)
    assert path.exists() and path.parent.name == artifacts.CHAINS_SUBDIR
    loaded = artifacts.load_chains("F9")
    assert loaded["chains"].shape == (4, 16, 5)
    assert np.allclose(loaded["wave"], res.wave)
    assert loaded["param_names"].tolist() == res.param_names


# -- known-answer recovery (needs bing + emcee) -----------------------------
def _synth_rrs(config, wave, truth_lin, Chl):
    """Build a noise-free Rrs from known linear params via BING's forward model."""
    import bing.evaluate as ev
    from bing.models import utils as model_utils

    _, rt_dict, models = run.build_models(config, wave)
    model_utils.init_other_bits(models, Chl=np.array([Chl]), Y=None, Rrs=None)
    truth = np.asarray(truth_lin, dtype=float).copy()
    ii = 0
    for ss in (0, 1):
        for prior in models[ss].priors.priors:
            if prior.flavor.startswith("log"):
                truth[ii] = np.log10(truth[ii])
            ii += 1
    na = models[0].nparam
    rrs = np.squeeze(
        ev.calc_Rrs_from_models(models[0], truth[:na], models[1], truth[na:], rt_dict)
    )
    return np.asarray(rrs, dtype=float)


def test_fit_spectrum_recovers_bbp():
    pytest.importorskip("bing")
    pytest.importorskip("emcee")
    np.random.seed(0)
    # short MCMC for speed; small analysis_burn so the chain isn't emptied
    config = FitConfig(nsteps=1000, nburn=300, analysis_burn=300)
    wave = np.arange(405.0, 700.0, 8.0)
    Chl = 0.1
    # truth: Adg, Sdg, Aph, Bnw, beta
    truth = [0.02, 0.017, 0.03, 0.004, 1.0]
    # ExpBricaud.set_aph loads an external Loisel aph-basis file; skip cleanly
    # where bing is installed but that data is not present (e.g. lean CI).
    try:
        rrs = _synth_rrs(config, wave, truth, Chl)
        result = run.fit_spectrum(wave, rrs, 0.02 * rrs, Chl=Chl, config=config)
    except FileNotFoundError as exc:
        pytest.skip(f"BING aph-basis data unavailable: {exc}")
    bbp700 = next(q for q in result.quantities if q["quantity"] == "bbp700")
    # Pow: bb_nw(700) = Bnw*(600/700)^beta = 0.004*(6/7) ≈ 3.43e-3
    assert bbp700["value"] == pytest.approx(0.004 * (600.0 / 700.0), rel=0.3)
    assert bbp700["value_lo"] < bbp700["value"] < bbp700["value_hi"]
    assert 0.0 <= result.accept_frac <= 1.0
    assert result.chisq < 5.0  # near-perfect fit to a noise-free spectrum
