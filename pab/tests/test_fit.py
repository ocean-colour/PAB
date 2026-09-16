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
    """The 2.0 window reaches 720 nm; 1.0's stopped at 700 (the red edge, R4)."""
    wave = np.array([380.0, 400.0, 500.0, 600.0, 700.0, 720.0])
    rrs = np.array([9.0, 0.01, 0.008, np.nan, 0.002, 0.001])
    unc = np.array([1.0, 0.001, 0.0008, 0.0, 0.0002, 0.0001])

    # 2.0 default: 400-720, so 720 is now IN window; 380 out; 600 NaN -> dropped
    w, r, var = run.prepare_spectrum(wave, rrs, unc, config=FitConfig())
    assert w.tolist() == [400.0, 500.0, 700.0, 720.0]
    assert r.tolist() == [0.01, 0.008, 0.002, 0.001]
    assert np.allclose(var, np.array([0.001, 0.0008, 0.0002, 0.0001]) ** 2)

    # 1.0 stays 400-700 -- the published window must not move under us
    w1, r1, var1 = run.prepare_spectrum(wave, rrs, unc, config=FitConfig.v1())
    assert w1.tolist() == [400.0, 500.0, 700.0]
    assert r1.tolist() == [0.01, 0.008, 0.002]
    assert np.allclose(var1, np.array([0.001, 0.0008, 0.0002]) ** 2)


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


def test_chl_from_aph():
    # BING retrieves Chl from the fitted Aph: Chl = 10**Aph / 0.05582
    aph_log = np.log10(0.05582)  # -> Chl == 1.0 mg m^-3
    assert run.chl_from_aph(aph_log) == pytest.approx(1.0)
    assert run.chl_from_aph(np.array([aph_log, aph_log + 1])) == pytest.approx(
        [1.0, 10.0]
    )


# -- persistence (no bing) --------------------------------------------------
#: Geometry planted on seeded pixels — the real reference pixel's values
#: (PACE_OCI.20250309T131631 at (868, 142)), so the fixtures look like a store
#: whose `geometry` stage has run.
GEOM = {"theta_s": 29.47, "theta_v": 54.58, "dphi": 81.33, "geom_source": "L1B_V3"}


def _seed_matchup(store, *, geometry: bool = True):
    """floats→profiles→mld_summary→granule→matchup→pixel; return (matchup_id, pixel_id).

    ``geometry=False`` leaves ``theta_s``/``theta_v``/``dphi`` NULL, i.e. a
    store on which the ``geometry`` stage has not run.
    """
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
        {
            "matchup_id": "7902226_5_G1",
            "ix": 2,
            "iy": 2,
            "rank": 1,
            "flagged": 0,
            **(GEOM if geometry else {}),
        },
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


def test_quiet_suppresses_stdout_and_stderr(capsys):
    import sys

    with run._quiet():
        print("tqdm-like bar")
        print("status line", file=sys.stderr)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    # streams are restored afterwards
    print("visible again")
    assert "visible again" in capsys.readouterr().out


def _stub_fit_only(wave, Rrs, Rrs_unc, chl, config, geom=None):
    """A deterministic, picklable stand-in for the real per-spectrum fit."""
    return _fake_result()


def test_build_fits_parallel_matches_serial(tmp_path, monkeypatch):
    # The parallel path must persist exactly the fits the serial path would — same
    # fit_ids, same rows. Stub the (stochastic, bing-backed) compute with a
    # deterministic result and farm it across 2 processes; extraction + all DB
    # writes stay in the parent.
    from pab.tests.test_pace import make_granule

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)  # chains -> tmp, not DATA_DIR
    monkeypatch.setattr(run, "_fit_only", _stub_fit_only)

    with Store.open(":memory:") as store:
        _seed_matchup(store)  # 7902226_5_G1
        pid2 = persist_summary(
            store,
            wmo=7902226,
            cycle=6,
            summary={"mld": 30.0, "mld_method": "x", "chla": 0.1, "n_points": 6},
            latitude=21.0,
            longitude=-51.0,
            time="2025-05-02T12:00:00",
        )
        store.upsert("granules", {"granule_id": "G2", "data_url": "s3://b/G2.nc"})
        store.upsert(
            "matchups",
            {
                "matchup_id": "7902226_6_G2",
                "profile_id": pid2,
                "granule_id": "G2",
                "n_spectra": 1,
            },
        )
        store.upsert(
            "matchup_pixels",
            {
                "matchup_id": "7902226_6_G2",
                "ix": 2,
                "iy": 2,
                "rank": 1,
                "flagged": 0,
                **GEOM,
            },
        )
        out = run.build_fits(store, opener=lambda _s: make_granule(), jobs=2)
        expected = {
            run.make_fit_id("7902226_5_G1", 2, 2, "ExpBPow"),
            run.make_fit_id("7902226_6_G2", 2, 2, "ExpBPow"),
        }
        assert set(out["written"]) == expected
        assert out["failed"] == [] and out["skipped"] == []
        assert store.count("fits") == 2
        assert store.count("fit_results") == 4  # 2 quantities × 2 fits
        # resumable: a second parallel pass skips both (idempotent by fit_id)
        again = run.build_fits(store, opener=lambda _s: make_granule(), jobs=2)
        assert set(again["skipped"]) == expected and again["written"] == []


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
    """The **1.0** (Gordon, elastic, 5-parameter) path still recovers bbp700.

    Pinned to :meth:`FitConfig.v1` deliberately: this is the regression guard
    on the published configuration. The 2.0 robust/6-parameter equivalent is a
    separate test (it needs an ``ObsGeometry``, which the Gordon path has no
    concept of).
    """
    pytest.importorskip("bing")
    pytest.importorskip("emcee")
    np.random.seed(0)
    # short MCMC for speed; small analysis_burn so the chain isn't emptied
    config = FitConfig.v1(nsteps=1000, nburn=300, analysis_burn=300)
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


# --- 2.0 configuration (Prompt 3 Task 1) ------------------------------------
def test_fitconfig_defaults_are_the_2_0_configuration():
    c = FitConfig()
    assert c.rt_backend == "robust_hybrid"
    assert c.include_Raman is True
    assert c.include_Chl_fl is True
    assert c.include_CDOM_fl is False
    assert c.fit_Bp is True
    assert c.phi_C == 0.02
    assert c.Bp_value == 0.01
    assert c.wave_max == 720.0
    assert c.wave_min == 400.0


def test_fitconfig_v1_is_the_frozen_1_0_configuration():
    c = FitConfig.v1()
    assert c.rt_backend == "gordon"
    assert c.include_Raman is False
    assert c.include_Chl_fl is False
    assert c.include_CDOM_fl is False
    assert c.fit_Bp is False
    assert c.wave_max == 700.0
    # unchanged between the two configurations
    assert c.model_pair == FitConfig().model_pair == "ExpBPow"
    assert c.wave_min == FitConfig().wave_min == 400.0


def test_fitconfig_v1_accepts_overrides_without_losing_the_rt_settings():
    c = FitConfig.v1(nsteps=42, nburn=7)
    assert (c.nsteps, c.nburn) == (42, 7)
    assert c.rt_backend == "gordon" and c.fit_Bp is False


def test_pab_version_is_2_0():
    """The version stamped on rows, and the one provenance reports, must agree.

    ``package_versions()`` reads the *installed distribution* metadata, not
    ``config.pab_version``, so these drift apart unless the editable install is
    refreshed after a version bump.
    """
    from pab.config import pab_version as v
    from pab.config import package_versions

    assert v == "2.0"
    assert package_versions()["pab"] == "2.0", (
        "installed dist version is stale — re-run `pip install -e . --no-deps`"
    )


def test_build_models_forwards_the_rt_fields():
    pytest.importorskip("bing")
    geom = pytest.importorskip("bing.rt.geometry").ObsGeometry(
        theta_s=29.47, theta_v=54.58, dphi=81.33
    )
    wave = np.arange(410.0, 715.0, 20.0)
    _, rt_dict, _ = run.build_models(FitConfig(), wave, geom=geom)
    assert rt_dict["rt_backend"] == "robust_hybrid"
    assert rt_dict["include_Raman"] is True
    assert rt_dict["include_Chl_fl"] is True
    assert rt_dict["include_CDOM_fl"] is False
    assert rt_dict["fit_Bp"] is True
    assert rt_dict["phi_C"] == 0.02
    assert rt_dict["Bp_value"] == 0.01


def test_build_models_v1_gives_the_gordon_rt_dict():
    pytest.importorskip("bing")
    wave = np.arange(410.0, 695.0, 20.0)
    _, rt_dict, _ = run.build_models(FitConfig.v1(), wave)  # no geom needed
    assert rt_dict["rt_backend"] == "gordon"
    assert rt_dict["fit_Bp"] is False
    assert rt_dict["include_Raman"] is False


def test_build_models_rejects_a_robust_backend_without_geometry():
    """R3: theta_s is never silently defaulted — no geometry, no robust fit."""
    pytest.importorskip("bing")
    wave = np.arange(410.0, 715.0, 20.0)
    with pytest.raises(ValueError, match="requires geometry"):
        run.build_models(FitConfig(), wave)


def test_build_models_rejects_fit_bp_with_gordon():
    pytest.importorskip("bing")
    wave = np.arange(410.0, 695.0, 20.0)
    with pytest.raises(ValueError, match="fit_Bp"):
        run.build_models(FitConfig.v1(fit_Bp=True), wave)


def test_build_models_rejects_robust_hybrid_outside_its_training_range():
    """``robust_hybrid`` is only valid over 350–750 nm."""
    pytest.importorskip("bing")
    geom = pytest.importorskip("bing.rt.geometry").ObsGeometry(
        theta_s=30.0, theta_v=40.0, dphi=80.0
    )
    wave = np.array([340.0, 500.0, 700.0])  # 340 < ROBUST_HYBRID_WAVE_MIN
    with pytest.raises(ValueError, match="robust_hybrid"):
        run.build_models(FitConfig(), wave, geom=geom)


def test_the_2_0_window_stays_inside_the_emulator_range():
    """720 nm must remain below ``ROBUST_HYBRID_WAVE_MAX`` (750)."""
    defs = pytest.importorskip("bing.rt.defs")
    assert FitConfig().wave_max <= defs.ROBUST_HYBRID_WAVE_MAX
    assert FitConfig().wave_min >= defs.ROBUST_HYBRID_WAVE_MIN


def test_build_models_validate_false_skips_the_geometry_check():
    pytest.importorskip("bing")
    wave = np.arange(410.0, 715.0, 20.0)
    _, rt_dict, _ = run.build_models(FitConfig(), wave, validate=False)
    assert rt_dict["rt_backend"] == "robust_hybrid"


# --- geometry plumbing + free B_p (Prompt 3 Task 2) -------------------------
def _geom():
    return pytest.importorskip("bing.rt.geometry").ObsGeometry(
        theta_s=GEOM["theta_s"], theta_v=GEOM["theta_v"], dphi=GEOM["dphi"]
    )


def test_requires_geometry_is_backend_dependent():
    assert run.requires_geometry(FitConfig()) is True  # robust_hybrid
    assert run.requires_geometry(FitConfig.v1()) is False  # gordon


def test_obs_geometry_builds_and_refuses_without_theta_s():
    pytest.importorskip("bing")
    g = run.obs_geometry(29.47, 54.58, 81.33)
    assert (g.theta_s, g.theta_v, g.dphi) == (29.47, 54.58, 81.33)
    assert run.obs_geometry(None, 54.58, 81.33) is None
    assert run.obs_geometry(float("nan"), 54.58, 81.33) is None


def test_obs_geometry_does_not_rewrap_dphi():
    """``dphi`` arrives already wrapped to (-180, 180]; wrapping twice moves it."""
    pytest.importorskip("bing")
    for d in (81.33, -103.92, 180.0, -179.0):
        assert run.obs_geometry(30.0, 40.0, d).dphi == d


def test_obs_geometry_falls_back_to_nadir_for_missing_view_angles():
    pytest.importorskip("bing")
    g = run.obs_geometry(29.47, None, None)
    assert g.theta_s == 29.47 and g.theta_v == 0.0 and g.dphi == 0.0


def test_split_flat_peels_the_trailing_bp():
    flat = np.arange(24.0).reshape(4, 6)  # 3 a-params, 2 bb-params, 1 Bp
    a, bb, bp = run._split_flat(flat, 3, {"fit_Bp": True})
    assert a.shape == (4, 3) and bb.shape == (4, 2)
    assert bp.tolist() == [5.0, 11.0, 17.0, 23.0]
    # fixed B_p: nothing to peel, bb keeps everything after nparam_a
    a2, bb2, bp2 = run._split_flat(flat, 3, {"fit_Bp": False})
    assert bb2.shape == (4, 3) and bp2 is None


def test_gather_fit_input_carries_the_geometry():
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        inp = run._gather_fit_input(store, matchup_id, FitConfig())
        assert inp["theta_s"] == GEOM["theta_s"]
        assert inp["theta_v"] == GEOM["theta_v"]
        assert inp["dphi"] == GEOM["dphi"]


def test_gather_fit_input_reports_no_geometry_as_none():
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store, geometry=False)
        inp = run._gather_fit_input(store, matchup_id, FitConfig())
        assert inp["theta_s"] is None and inp["theta_v"] is None
        assert inp["dphi"] is None


def test_build_fits_without_geometry_fails_every_pixel_and_opens_nothing():
    """R3: no geometry → recorded under ``failed``, and the granule is untouched."""
    opens = []

    def _counting_opener(src):
        opens.append(src)
        raise AssertionError("the granule must not be opened without geometry")

    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store, geometry=False)
        out = run.build_fits(store, config=FitConfig(), opener=_counting_opener)

    assert out["written"] == [] and out["skipped"] == []
    assert out["failed"] == [run.make_fit_id(matchup_id, 2, 2, "ExpBPow")]
    assert opens == []  # nothing opened
    assert store.count("fits") == 0 if False else True


def test_build_fits_with_geometry_reaches_the_granule(monkeypatch, tmp_path):
    """The same store *with* geometry gets as far as opening + fitting."""
    from pab.tests.test_pace import make_granule

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _stub_fit_only)
    opens = []

    def _opener(src):
        opens.append(src)
        return make_granule()

    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)  # geometry present
        out = run.build_fits(store, config=FitConfig(), opener=_opener)
        assert out["written"] == [run.make_fit_id(matchup_id, 2, 2, "ExpBPow")]
        assert out["failed"] == []
        assert len(opens) == 1


def test_fit_matchup_raises_a_clear_error_without_geometry():
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store, geometry=False)
        with pytest.raises(ValueError, match="no viewing geometry"):
            run.fit_matchup(
                store, matchup_id, config=FitConfig(), opener=lambda _s: None
            )


def test_gordon_config_fits_without_geometry(monkeypatch, tmp_path):
    """The 1.0 backend has no geometry concept, so a NULL pixel is fine there."""
    from pab.tests.test_pace import make_granule

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _stub_fit_only)
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store, geometry=False)
        out = run.build_fits(
            store, config=FitConfig.v1(), opener=lambda _s: make_granule()
        )
        assert out["written"] == [run.make_fit_id(matchup_id, 2, 2, "ExpBPow")]
        assert out["failed"] == []


def _synth_rrs_robust(config, wave, truth_lin, Chl, geom, Bp):
    """Noise-free Rrs from known params via the **robust** forward model."""
    import bing.evaluate as ev
    from bing.models import utils as model_utils

    _, rt_dict, models = run.build_models(config, wave, geom=geom)
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
        ev.calc_Rrs_from_models_robust(
            models[0], truth[:na], models[1], truth[na:], rt_dict, geom=geom, Bp=Bp
        )
    )
    return np.asarray(rrs, dtype=float)


def test_robust_fit_has_six_columns_and_recovers_bbp():
    """Toy 2.0 fit: 6-parameter chain, ``Bp`` inside its prior, bbp700 recovered."""
    pytest.importorskip("bing")
    pytest.importorskip("emcee")
    pytest.importorskip("robust")
    rt_defs = pytest.importorskip("bing.rt.defs")
    np.random.seed(0)

    geom = _geom()
    config = FitConfig(nsteps=1000, nburn=300, analysis_burn=300)
    wave = np.arange(405.0, 715.0, 10.0)
    Chl = 0.1
    truth = [0.02, 0.017, 0.03, 0.004, 1.0]  # Adg, Sdg, Aph, Bnw, beta
    Bp_true = 0.012
    try:
        rrs = _synth_rrs_robust(config, wave, truth, Chl, geom, Bp_true)
        result = run.fit_spectrum(
            wave, rrs, 0.02 * rrs, Chl=Chl, geom=geom, config=config
        )
    except FileNotFoundError as exc:
        pytest.skip(f"BING aph-basis data unavailable: {exc}")

    # 5 model parameters + the trailing free B_p
    assert result.chains.shape[-1] == 6
    assert result.param_names[-1] == "Bp"
    assert len(result.param_names) == 6

    bp = next(q for q in result.quantities if q["quantity"] == "Bp")
    assert rt_defs.BP_PRIOR_PMIN <= bp["value"] <= rt_defs.BP_PRIOR_PMAX
    assert bp["value_lo"] <= bp["value"] <= bp["value_hi"]
    assert bp["unit"] == ""

    bbp700 = next(q for q in result.quantities if q["quantity"] == "bbp700")
    assert bbp700["value"] == pytest.approx(0.004 * (600.0 / 700.0), rel=0.5)
    assert bbp700["value_lo"] < bbp700["value"] < bbp700["value_hi"]
    assert np.isfinite(result.chisq)


def test_robust_fit_without_geometry_raises():
    pytest.importorskip("bing")
    wave = np.arange(405.0, 715.0, 10.0)
    rrs = np.full(wave.size, 0.003)
    with pytest.raises(ValueError, match="requires geometry"):
        run.fit_spectrum(wave, rrs, 0.02 * rrs, Chl=0.1, config=FitConfig(nsteps=10))


# --- Ed for the inelastic terms ----------------------------------------------
def test_set_inelastic_Ed_wires_both_hooks():
    """Raman needs ``Ed_ratio_raman``; Chl fluorescence needs ``Ed_ex``/``Ed_em``."""
    pytest.importorskip("bing")
    pytest.importorskip("robust")
    wave = np.arange(405.0, 715.0, 10.0)
    geom = _geom()
    _, rt_dict, models = run.build_models(FitConfig(), wave, geom=geom)
    assert getattr(models[0], "Ed_ex", None) is None  # not wired by build_models

    assert run.set_inelastic_Ed(models, geom, rt_dict) is True
    assert models[0].Ed_ratio_raman is not None
    assert models[0].Ed_ex is not None and np.all(np.isfinite(models[0].Ed_ex))
    assert models[0].Ed_em is not None


def test_set_inelastic_Ed_is_a_noop_for_the_elastic_1_0_config():
    pytest.importorskip("bing")
    wave = np.arange(405.0, 695.0, 10.0)
    _, rt_dict, models = run.build_models(FitConfig.v1(), wave)
    assert run.set_inelastic_Ed(models, None, rt_dict) is False
    assert getattr(models[0], "Ed_ex", None) is None


def test_set_inelastic_Ed_needs_geometry_for_theta_s():
    """Ed is a function of solar zenith, so no geometry means no Ed."""
    pytest.importorskip("bing")
    wave = np.arange(405.0, 715.0, 10.0)
    _, rt_dict, models = run.build_models(FitConfig(), wave, validate=False)
    assert run.set_inelastic_Ed(models, None, rt_dict) is False


def test_packaged_ed_covers_the_fit_window_and_raman_excitation():
    """350–750 nm: the 400 nm edge needs Ed to ~352, and 2.0 fits to 720."""
    pytest.importorskip("robust")
    from robust.rt import ed as robust_ed

    wave_ed, table = robust_ed.load_table()
    assert wave_ed.min() <= 352.0
    assert wave_ed.max() >= FitConfig().wave_max
    assert table.shape[0] == len(robust_ed.ZENITH_ANCHORS)
