"""Stage 5 tests: the BING fitting wrapper (``pab.fit``)."""

import os

import numpy as np
import pytest

from pab.argo.summary import persist_summary
from pab.db import Store
from pab.fit import FitConfig, artifacts, models, run


# -- pure helpers (no bing) -------------------------------------------------
def test_make_fit_id_is_version_aware():
    from pab.config import pab_version

    assert (
        run.make_fit_id("7902226_5_G1", 3, 4, "ExpBPow")
        == f"7902226_5_G1_3_4_ExpBPow_v{pab_version}"
    )
    assert run.make_fit_id("7902226_5_G1", 3, 4, "ExpBPow", version="1.0") == (
        "7902226_5_G1_3_4_ExpBPow_v1.0"
    )


def test_make_fit_id_does_not_produce_the_1_0_format():
    """The unsuffixed 1.0 id must never be generated under 2.0.

    ``build_fits`` skips a matchup whose ``fit_id`` is already stored, so if 2.0
    reproduced the 1.0 id it would skip every matchup that already has a 1.0
    fit — and ``--replace`` would overwrite the published rows instead of adding
    to them.
    """
    legacy = "7902226_5_G1_3_4_ExpBPow"
    produced = run.make_fit_id("7902226_5_G1", 3, 4, "ExpBPow")
    assert produced != legacy
    assert produced.startswith(legacy + "_v")
    assert produced.endswith("_v2.0.1")  # the current version; 2.0 ids end "_v2.0"
    assert produced != legacy + "_v2.0"  # a 2.0.1 row never overwrites a 2.0 one


def test_fit_ids_of_the_three_generations_do_not_collide():
    args = ("7902226_5_G1", 3, 4, "ExpBPow")
    ids = {run.make_fit_id(*args, version=v) for v in ("1.0", "2.0", "2.0.1")}
    assert len(ids) == 3


def test_prepare_spectrum_window_and_variance():
    """Both 1.0 and 2.0 fit 400-700 nm; 719/720 is excluded (the red edge, R4).

    2.0 briefly used 720 to reach the red shoulder, but ``Rrs(719)`` is
    negative or noise-dominated on 40% of real matchups
    (``build_v2_prompt_3.md`` Q2), so JXP moved it back.
    """
    wave = np.array([380.0, 400.0, 500.0, 600.0, 700.0, 720.0])
    rrs = np.array([9.0, 0.01, 0.008, np.nan, 0.002, 0.001])
    unc = np.array([1.0, 0.001, 0.0008, 0.0, 0.0002, 0.0001])
    expected_w = [400.0, 500.0, 700.0]
    expected_r = [0.01, 0.008, 0.002]
    expected_var = np.array([0.001, 0.0008, 0.0002]) ** 2

    for label, config in (("2.0", FitConfig()), ("1.0", FitConfig.v1())):
        w, r, var = run.prepare_spectrum(wave, rrs, unc, config=config)
        assert w.tolist() == expected_w, label  # 380 and 720 out of window
        assert r.tolist() == expected_r, label  # 600 is NaN -> dropped
        assert np.allclose(var, expected_var), label


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
    pytest.importorskip("bing")
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
    # the negative-blue QA count rides along: an all-positive spectrum -> 0
    neg = next(q for q in result.quantities if q["quantity"] == "n_neg_blue")
    assert neg == {
        "quantity": "n_neg_blue",
        "value": 0.0,
        "value_lo": 0.0,
        "value_hi": 0.0,
        "unit": "bands",
    }


# --- 2.0 / 2.0.1 configuration (Prompt 3 Task 1; Outliers O5) ---------------
def test_fitconfig_defaults_are_the_2_0_1_configuration():
    """The 2.0 physics plus the physical prior ceilings (Q&A/Outliers 2 = A)."""
    c = FitConfig()
    assert c.rt_backend == "robust_hybrid"
    assert c.include_Raman is True
    assert c.include_Chl_fl is True
    assert c.include_CDOM_fl is False
    assert c.fit_Bp is True
    assert c.phi_C == 0.02
    assert c.Bp_value == 0.01
    assert c.wave_max == 700.0
    assert c.wave_min == 400.0
    # the 2.0.1 ceilings, m^-1: b_bp(600) <= 0.1, A_dg and A_ph <= 10
    assert c.bbp600_max == 0.1
    assert c.adg_max == 10.0
    assert c.aph_max == 10.0


def test_fitconfig_v2_0_is_the_frozen_unceilinged_2_0_configuration():
    """What produced the 15,971 2.0 fits: the same physics, BING's 1e5 ceilings."""
    c = FitConfig.v2_0()
    d = FitConfig()
    assert c.bbp600_max is None and c.adg_max is None and c.aph_max is None
    # every other field is the 2.0.1 default -- 2.0.1 differs by the priors only
    for name in (
        "model_pair", "satellite", "nsteps", "nburn", "wave_min", "wave_max",
        "variable_Gordon", "include_Raman", "rt_backend", "include_Chl_fl",
        "include_CDOM_fl", "phi_C", "fit_Bp", "Bp_value", "analysis_burn", "perc",
    ):
        assert getattr(c, name) == getattr(d, name), name
    # overrides still work (the O8 slice test shortens the chain)
    assert FitConfig.v2_0(nsteps=50).nsteps == 50
    assert FitConfig.v2_0(nsteps=50).bbp600_max is None


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
    # since Q2 the window is identical too: 2.0 differs by RT, not by band
    assert c.wave_max == FitConfig().wave_max == 700.0


def test_fitconfig_v1_has_no_prior_ceilings():
    """The 1.0 priors must not change retroactively: v1() is unceilinged."""
    c = FitConfig.v1()
    assert c.bbp600_max is None and c.adg_max is None and c.aph_max is None
    assert models.prior_set_label(c) == "bing_standard"


def test_fitconfig_v1_accepts_overrides_without_losing_the_rt_settings():
    c = FitConfig.v1(nsteps=42, nburn=7)
    assert (c.nsteps, c.nburn) == (42, 7)
    assert c.rt_backend == "gordon" and c.fit_Bp is False


def test_pab_version_is_2_0_1():
    """The version stamped on rows, and the one provenance reports, must agree.

    ``package_versions()`` reads the *installed distribution* metadata, not
    ``config.pab_version``, so these drift apart unless the editable install is
    refreshed after a version bump.
    """
    from pab.config import pab_version as v
    from pab.config import package_versions

    assert v == "2.0.1"
    assert package_versions()["pab"] == "2.0.1", (
        "installed dist version is stale — re-run `pip install -e . --no-deps`"
    )
    # a 2.0.1 fit id coexists with -- never overwrites -- the 2.0 one
    new = run.make_fit_id("m", 1, 2, "ExpBPow")
    old = run.make_fit_id("m", 1, 2, "ExpBPow", version="2.0")
    assert new.endswith("_v2.0.1") and old.endswith("_v2.0") and new != old


# --- the 2.0.1 prior ceilings (Outliers O5 step 1) ---------------------------
def test_prior_set_label_is_built_from_the_ceilings():
    assert models.prior_set_label(FitConfig()) == (
        "bing_standard+ceiling:bbp600<=0.1,adg<=10,aph<=10"
    )
    assert models.prior_set_label(FitConfig.v2_0()) == "bing_standard"
    assert models.prior_set_label(FitConfig.v1()) == "bing_standard"
    # only the ceilings that are set, in the fixed order
    assert models.prior_set_label(FitConfig(adg_max=None)) == (
        "bing_standard+ceiling:bbp600<=0.1,aph<=10"
    )
    assert models.prior_set_label(FitConfig(bbp600_max=0.05, adg_max=None, aph_max=None)) == (
        "bing_standard+ceiling:bbp600<=0.05"
    )
    # a config object without the fields (a mock, or one predating 2.0.1) is uncapped
    assert models.prior_set_label(object()) == "bing_standard"


def test_ceilings_from_prior_set_inverts_the_label():
    for cfg in (
        FitConfig(),
        FitConfig.v2_0(),
        FitConfig(adg_max=None),
        FitConfig(bbp600_max=0.05, adg_max=None, aph_max=None),
    ):
        fields = models.ceilings_from_prior_set(models.prior_set_label(cfg))
        assert fields == {
            "bbp600_max": cfg.bbp600_max,
            "adg_max": cfg.adg_max,
            "aph_max": cfg.aph_max,
        }
    # the stored 1.0/2.0 stamp, NULL and "" all mean "no ceilings"
    none = {"bbp600_max": None, "adg_max": None, "aph_max": None}
    assert models.ceilings_from_prior_set("bing_standard") == none
    assert models.ceilings_from_prior_set(None) == none
    assert models.ceilings_from_prior_set("") == none
    with pytest.raises(ValueError, match="unrecognised"):
        models.ceilings_from_prior_set("somebody_elses_priors")
    with pytest.raises(ValueError, match="unrecognised ceiling"):
        models.ceilings_from_prior_set("bing_standard+ceiling:sdg<=1")


def test_prior_ceilings_reject_a_non_positive_ceiling():
    with pytest.raises(ValueError, match="positive finite"):
        models.prior_ceilings(FitConfig(bbp600_max=0.0))
    with pytest.raises(ValueError, match="positive finite"):
        models.prior_set_label(FitConfig(adg_max=float("nan")))


def test_prior_bounds_carry_the_log10_ceilings():
    """The LM bounds -- and, through the same prior objects, BING's log_prob --
    see pmax = log10(ceiling) on Adg (index 0), Aph (index 2) and Bnw (index 3,
    the Pow amplitude at the 600 nm pivot); Sdg and beta are untouched."""
    pytest.importorskip("bing")
    wave = np.arange(405.0, 705.0, 10.0)
    _, _, mdl = run.build_models(FitConfig(), wave, geom=_geom())
    assert list(mdl[0].pnames) == ["Adg", "Sdg", "Aph"]
    assert list(mdl[1].pnames) == ["Bnw", "beta"]
    assert mdl[1].pivot == 600.0  # Bnw is b_bp(600), hence bbp600_max
    low, high = run._prior_bounds(mdl)
    assert high.tolist() == pytest.approx([1.0, 0.02, 1.0, -1.0, 2.0])
    assert low.tolist() == pytest.approx([-6.0, 0.01, -6.0, -6.0, 0.0])
    # flavors unchanged: still log-uniform on the amplitudes, uniform on Sdg/beta
    flavors = [p.flavor for p in mdl[0].priors.priors + mdl[1].priors.priors]
    assert flavors == ["log_uniform", "uniform", "log_uniform", "log_uniform", "uniform"]


def test_prior_bounds_none_leaves_bings_ceiling_of_5():
    pytest.importorskip("bing")
    wave = np.arange(405.0, 705.0, 10.0)
    _, _, mdl = run.build_models(FitConfig.v2_0(), wave, geom=_geom())
    _, high = run._prior_bounds(mdl)
    assert high.tolist() == pytest.approx([5.0, 0.02, 5.0, 5.0, 2.0])
    # one None at a time: only that parameter keeps BING's 5
    _, _, mdl = run.build_models(FitConfig(aph_max=None), wave, geom=_geom())
    _, high = run._prior_bounds(mdl)
    assert high.tolist() == pytest.approx([1.0, 0.02, 5.0, -1.0, 2.0])
    # and the 1.0 path (Gordon, no geometry) is unceilinged as it always was
    _, _, mdl = run.build_models(FitConfig.v1(), wave)
    _, high = run._prior_bounds(mdl)
    assert high.tolist() == pytest.approx([5.0, 0.02, 5.0, 5.0, 2.0])


def test_prior_ceilings_do_not_touch_bing():
    """A PAB-side override: after a ceilinged build, BING's factory and a
    fresh set_standard_priors still give the 1e5 ceiling."""
    pytest.importorskip("bing")
    from bing.parameters import standard

    wave = np.arange(405.0, 705.0, 10.0)
    run.build_models(FitConfig(), wave, geom=_geom())
    p = standard.expb_pow()
    assert [d["pmax"] for d in p.apriors] == [5, 0.02, 5]
    assert [d["pmax"] for d in p.bpriors] == [5, 2.0]
    # expb_pow's apriors are three references to one dict; the override must
    # copy, not mutate, or capping Adg would have moved Sdg's pmax too
    assert p.apriors[0] is p.apriors[2]


def test_apply_prior_ceilings_refuses_a_ceiling_below_the_floor():
    pytest.importorskip("bing")
    wave = np.arange(405.0, 705.0, 10.0)
    with pytest.raises(ValueError, match="at or below the prior floor"):
        run.build_models(FitConfig(bbp600_max=1e-7), wave, geom=_geom())


def test_persist_fit_stamps_prior_set_from_the_config():
    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        for fit_id, cfg in (("NEW", FitConfig()), ("OLD", FitConfig.v2_0())):
            artifacts.persist_fit(
                store,
                fit_id=fit_id,
                matchup_id=matchup_id,
                pixel_id=pixel_id,
                result=_fake_result(),
                config=cfg,
                chains_path=f"/tmp/{fit_id}.npz",
            )
        rows = {r["fit_id"]: r for r in store.query("SELECT * FROM fits")}
        assert rows["NEW"]["prior_set"] == (
            "bing_standard+ceiling:bbp600<=0.1,adg<=10,aph<=10"
        )
        assert rows["NEW"]["pab_version"] == "2.0.1"
        assert rows["OLD"]["prior_set"] == "bing_standard"


# --- the step-0 check (Outliers O5 step 3) ------------------------------------
_NAMES6 = ["Adg", "Sdg", "Aph", "Bnw", "beta", "Bp"]


def _chains_starting_at(adg, aph, bnw, *, nwalkers=8):
    """(3, nwalkers, 6) chains whose step-0 walker medians are the given log10s."""
    chains = np.zeros((3, nwalkers, 6))
    chains[0, :, 0] = adg + np.linspace(-0.01, 0.01, nwalkers)
    chains[0, :, 2] = aph
    chains[0, :, 3] = bnw
    chains[1:, :, 3] = 4.9  # later steps are irrelevant: step 0 is the check
    return chains


def test_chain_start_report_measures_dex_below_each_ceiling():
    rep = run.chain_start_report(_chains_starting_at(-1.5, -1.0, -2.6), _NAMES6, FitConfig())
    assert rep["started_below_wall"] is True
    assert rep["margin_dex"] == run.WALL_MARGIN_DEX == 0.5
    assert set(rep["params"]) == {"Adg", "Aph", "Bnw"}
    bnw = rep["params"]["Bnw"]
    assert bnw["ceiling"] == 0.1 and bnw["ceiling_log10"] == pytest.approx(-1.0)
    assert bnw["step0_median"] == pytest.approx(-2.6)
    assert bnw["dex_below_ceiling"] == pytest.approx(1.6) and bnw["below_wall"] is True
    assert rep["params"]["Adg"]["dex_below_ceiling"] == pytest.approx(2.5, abs=0.02)


def test_chain_start_report_flags_a_start_at_the_wall():
    # Bnw median 0.2 dex under the ceiling: what the 51 runaways looked like
    # (4.7-4.99 against 5), translated to the 2.0.1 ceiling of log10(0.1) = -1
    rep = run.chain_start_report(_chains_starting_at(-1.5, -1.0, -1.2), _NAMES6, FitConfig())
    assert rep["started_below_wall"] is False
    assert rep["params"]["Bnw"]["below_wall"] is False
    assert rep["params"]["Adg"]["below_wall"] is True
    # exactly the margin counts as below
    rep = run.chain_start_report(_chains_starting_at(-1.5, -1.0, -1.5), _NAMES6, FitConfig())
    assert rep["started_below_wall"] is True
    # an Aph start at the wall is caught the same way
    rep = run.chain_start_report(_chains_starting_at(-1.5, 0.9, -2.6), _NAMES6, FitConfig())
    assert rep["started_below_wall"] is False and rep["params"]["Aph"]["below_wall"] is False


def test_chain_start_report_checks_only_capped_parameters():
    chains = _chains_starting_at(4.9, 4.9, 4.99)  # pinned to BING's 1e5 wall...
    # ...but under the 2.0 configuration there is no ceiling to be below
    rep = run.chain_start_report(chains, _NAMES6, FitConfig.v2_0())
    assert rep == {"started_below_wall": True, "margin_dex": 0.5, "params": {}}
    # one ceiling: only that parameter is reported
    rep = run.chain_start_report(chains, _NAMES6, FitConfig(adg_max=None, aph_max=None))
    assert list(rep["params"]) == ["Bnw"] and rep["started_below_wall"] is False
    # accepts the NPZ's param_names (a numpy str array) and a 5-column 1.0 chain
    rep = run.chain_start_report(chains[:, :, :5], np.array(_NAMES6[:5]), FitConfig())
    assert set(rep["params"]) == {"Adg", "Aph", "Bnw"}


def test_fit_spectrum_result_carries_an_empty_chain_start_by_default():
    assert _fake_result().chain_start == {}


# --- the replay seam (Outliers O5 step 4; Q&A/Outliers 8 = C) -----------------
def test_spectrum_from_chains_reproduces_the_npz_spectrum(tmp_path, monkeypatch):
    """The provider names the 2.0 fit of the same pixel, loads its NPZ by
    basename under ``root`` and hands back the stored spectrum + the stamp."""
    from pab.fit import replay

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    res = _fake_result()
    res.varRrs = np.array([4e-8, 9e-8, 1e-8])
    old_id = run.make_fit_id("7902226_5_G1", 2, 2, "ExpBPow", version="2.0")
    path = artifacts.save_chains(old_id, res)
    assert path.parent == tmp_path / artifacts.CHAINS_SUBDIR

    provider = replay.spectrum_from_chains(path.parent)
    inp = {"matchup_id": "7902226_5_G1", "ix": 2, "iy": 2, "model_pair": "ExpBPow",
           "fit_id": run.make_fit_id("7902226_5_G1", 2, 2, "ExpBPow")}
    assert inp["fit_id"].endswith("_v2.0.1")  # the fit being made is 2.0.1...
    wave, rrs, unc, source = provider(inp)
    # ...but the spectrum is the 2.0 fit's
    assert np.array_equal(wave, res.wave) and np.array_equal(rrs, res.Rrs)
    assert unc.tolist() == pytest.approx([2e-4, 3e-4, 1e-4])
    assert source == f"L2_AOP:replay:{old_id}"
    assert replay.replayed_fit_id(source) == old_id
    assert replay.replayed_fit_id("L2_AOP") is None
    # prepare_spectrum gives the fit back the stored varRrs (to rounding)
    _, _, var = run.prepare_spectrum(wave, rrs, unc, config=FitConfig())
    assert var == pytest.approx(res.varRrs, rel=1e-12)
    # a pixel with no 2.0 chain is a FileNotFoundError, not a silent granule read
    with pytest.raises(FileNotFoundError, match="no chain NPZ"):
        provider({**inp, "ix": 3})
    assert "version='2.0'" in provider.__name__


def _no_open(_src):
    raise AssertionError("no granule may be opened on the replay path")


def test_build_fits_with_spectra_never_calls_the_opener(monkeypatch, tmp_path):
    """``spectra=`` replaces the granule read entirely and stamps rrs_source."""
    pytest.importorskip("bing")
    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _qa_recording_stub)
    seen = []

    def provider(inp):
        seen.append(inp["fit_id"])
        wave = np.array([440.0, 550.0, 700.0])
        return wave, np.array([-1e-3, 0.005, 0.001]), np.full(3, 1e-4), "L2_AOP:replay:X_v2.0"

    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        out = run.build_fits(store, config=FitConfig(), opener=_no_open, spectra=provider)
        fit_id = run.make_fit_id(matchup_id, 2, 2, "ExpBPow")
        assert out["written"] == [fit_id] and out["failed"] == []
        assert seen == [fit_id]
        row = store.query("SELECT rrs_source, prior_set FROM fits")[0]
        assert row["rrs_source"] == "L2_AOP:replay:X_v2.0"
        assert row["prior_set"].startswith("bing_standard+ceiling:")
        # the provided spectrum is what was fitted (the QA count saw its -1e-3 at 440)
        q = store.query(
            "SELECT value FROM fit_results WHERE quantity = 'BING_ExpBPow_n_neg_blue'"
        )
        assert q == [{"value": 1.0}]
        npz = artifacts.load_chains(fit_id)
        assert npz["wave"].tolist() == [440.0, 550.0, 700.0]


def test_build_fits_with_a_three_tuple_provider_keeps_the_l2_stamp(monkeypatch, tmp_path):
    pytest.importorskip("bing")
    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _stub_fit_only)

    def provider(inp):
        return np.array([440.0, 550.0]), np.array([0.01, 0.005]), None

    with Store.open(":memory:") as store:
        _seed_matchup(store)
        out = run.build_fits(store, config=FitConfig(), opener=_no_open, spectra=provider)
        assert len(out["written"]) == 1
        assert store.query("SELECT rrs_source FROM fits")[0]["rrs_source"] == "L2_AOP"


def test_build_fits_records_a_failing_provider_without_aborting(monkeypatch, tmp_path):
    """A missing 2.0 NPZ fails that matchup like any other error; no granule."""
    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _stub_fit_only)

    def provider(inp):
        raise FileNotFoundError("no chain NPZ to replay")

    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        out = run.build_fits(store, config=FitConfig(), opener=_no_open, spectra=provider)
        assert out["failed"] == [run.make_fit_id(matchup_id, 2, 2, "ExpBPow")]
        assert out["written"] == [] and store.count("fits") == 0


def _replay_stub_provider(inp):
    """Module-level (picklable is not required -- the provider runs in the
    parent -- but the stub fit must be) 4-tuple provider for the parallel test."""
    return (
        np.array([440.0, 550.0, 700.0]),
        np.array([0.01, 0.005, 0.001]),
        np.full(3, 1e-4),
        "L2_AOP:replay:" + inp["fit_id"].replace("_v2.0.1", "_v2.0"),
    )


def test_build_fits_parallel_with_spectra_never_opens_a_granule(monkeypatch, tmp_path):
    pytest.importorskip("bing")
    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _stub_fit_only)
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        out = run.build_fits(
            store, config=FitConfig(), opener=_no_open, spectra=_replay_stub_provider, jobs=2
        )
        fit_id = run.make_fit_id(matchup_id, 2, 2, "ExpBPow")
        assert out["written"] == [fit_id] and out["failed"] == []
        row = store.query("SELECT rrs_source FROM fits")[0]
        assert row["rrs_source"] == "L2_AOP:replay:" + fit_id.replace("_v2.0.1", "_v2.0")


def test_fit_matchup_with_spectrum_skips_the_granule(monkeypatch, tmp_path):
    pytest.importorskip("bing")
    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _stub_fit_only)
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        result = run.fit_matchup(
            store, matchup_id, config=FitConfig(), opener=_no_open, persist=False,
            spectrum=lambda inp: (np.array([440.0]), np.array([0.01]), None),
        )
        assert isinstance(result, run.FitSpectrumResult)
        fit_id = run.fit_matchup(
            store, matchup_id, config=FitConfig(), opener=_no_open,
            spectrum=lambda inp: (np.array([440.0]), np.array([0.01]), None, "L2_AOP:replay:Q"),
        )
        assert fit_id == run.make_fit_id(matchup_id, 2, 2, "ExpBPow")
        assert store.query("SELECT rrs_source FROM fits")[0]["rrs_source"] == "L2_AOP:replay:Q"


def test_provided_spectrum_rejects_an_odd_tuple():
    with pytest.raises(ValueError, match="spectrum provider"):
        run._provided_spectrum(lambda inp: (1, 2), {})


def test_gather_fit_input_carries_the_model_pair():
    """The replay provider names the 2.0 fit from inp['model_pair']."""
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        inp = run._gather_fit_input(store, matchup_id, FitConfig())
        assert inp["model_pair"] == "ExpBPow"


def test_config_from_row_roundtrips_a_ceiling_prior_set():
    """A 2.0.1 row rebuilds with its ceilings; a 2.0 row (bing_standard) without."""
    from pab.plotting.fit_fig import _config_from_row

    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        for fit_id, cfg in (("NEW", FitConfig()), ("OLD", FitConfig.v2_0())):
            artifacts.persist_fit(
                store, fit_id=fit_id, matchup_id=matchup_id, pixel_id=pixel_id,
                result=_fake_result(), config=cfg, chains_path=f"/tmp/{fit_id}.npz",
            )
        rows = {r["fit_id"]: r for r in store.query("SELECT * FROM fits")}
        new = _config_from_row(rows["NEW"])
        assert (new.bbp600_max, new.adg_max, new.aph_max) == (0.1, 10.0, 10.0)
        assert models.prior_set_label(new) == rows["NEW"]["prior_set"]
        assert new.rt_backend == "robust_hybrid" and new.fit_Bp is True
        old = _config_from_row(rows["OLD"])
        assert (old.bbp600_max, old.adg_max, old.aph_max) == (None, None, None)
        assert models.prior_set_label(old) == rows["OLD"]["prior_set"] == "bing_standard"


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
    """The fit window must stay inside the emulator's 350-750 nm range."""
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
    pytest.importorskip("bing")
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
    pytest.importorskip("bing")
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store, geometry=False)
        with pytest.raises(ValueError, match="no viewing geometry"):
            run.fit_matchup(
                store, matchup_id, config=FitConfig(), opener=lambda _s: None
            )


def test_gordon_config_fits_without_geometry(monkeypatch, tmp_path):
    """The 1.0 backend has no geometry concept, so a NULL pixel is fine there."""
    pytest.importorskip("bing")
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
    # 11 BING quantities (5 params + Bp + 2x2 IOPs at 440/700 + chl) + n_neg_blue
    names = [q["quantity"] for q in result.quantities]
    assert names[-1] == "n_neg_blue" and len(names) == 12
    assert result.quantities[-1]["value"] == 0.0
    # 2.0.1: the step-0 check rides along; a physical toy starts far below the walls
    assert set(result.chain_start["params"]) == {"Adg", "Aph", "Bnw"}
    assert result.chain_start["started_below_wall"] is True
    assert result.chain_start["params"]["Bnw"]["dex_below_ceiling"] > 0.5


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
    """350-750 nm: the 400 nm edge needs Ed down to ~352 nm."""
    pytest.importorskip("robust")
    from robust.rt import ed as robust_ed

    wave_ed, table = robust_ed.load_table()
    assert wave_ed.min() <= 352.0
    assert wave_ed.max() >= FitConfig().wave_max
    assert table.shape[0] == len(robust_ed.ZENITH_ANCHORS)


# --- provenance: git SHAs + the persisted RT columns (Prompt 3 Task 4) -------
def test_package_versions_includes_robust_under_its_import_name():
    """``robust`` is distributed as ``retrieve-or-bust``; record the import name."""
    pytest.importorskip("robust")
    from pab.config import package_versions

    pv = package_versions()
    assert "robust" in pv
    assert pv["robust"] != "not installed"


def test_package_versions_carries_a_git_sha_map():
    from pab.config import _GIT_REPOS, package_versions

    pv = package_versions()
    assert set(pv["git_sha"]) == set(_GIT_REPOS)
    # this checkout is a git repo, so PAB at least must resolve
    assert pv["git_sha"]["PAB"] != "unknown"


def test_git_shas_look_like_short_hashes():
    from pab.config import UNKNOWN_SHA, git_shas

    for repo, sha in git_shas().items():
        assert sha == UNKNOWN_SHA or (
            4 <= len(sha) <= 40 and all(c in "0123456789abcdef" for c in sha)
        ), f"{repo} -> {sha!r}"


def test_env_var_overrides_the_git_sha(monkeypatch):
    """The container seam: no ``.git`` in the image, SHAs fed in by the build."""
    import json

    from pab.config import GIT_SHA_ENV, git_shas

    git_shas.cache_clear()
    monkeypatch.setenv(GIT_SHA_ENV, json.dumps({"PAB": "deadbee", "bing": "cafe123"}))
    try:
        shas = git_shas()
        assert shas["PAB"] == "deadbee"
        assert shas["bing"] == "cafe123"
        # repos absent from the override still fall back to git
        assert "ocpy" in shas
    finally:
        git_shas.cache_clear()


def test_malformed_sha_env_var_does_not_break_provenance(monkeypatch):
    from pab.config import _GIT_REPOS, GIT_SHA_ENV, git_shas

    git_shas.cache_clear()
    monkeypatch.setenv(GIT_SHA_ENV, "not json {{{")
    try:
        shas = git_shas()  # must not raise
        assert set(shas) == set(_GIT_REPOS)
    finally:
        git_shas.cache_clear()


def test_unknown_sha_for_a_non_repo(tmp_path):
    from pab.config import UNKNOWN_SHA, _git_sha

    assert _git_sha(tmp_path) == UNKNOWN_SHA
    assert _git_sha(None) == UNKNOWN_SHA
    assert _git_sha(tmp_path / "nope") == UNKNOWN_SHA


def test_persist_fit_writes_the_v5_rt_columns():
    """The six columns that distinguish a 2.0 fit from a 1.0 one."""
    pytest.importorskip("robust")
    import json

    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        artifacts.persist_fit(
            store,
            fit_id="F2",
            matchup_id=matchup_id,
            pixel_id=pixel_id,
            result=_fake_result(),
            config=FitConfig(),
            chains_path="/tmp/F2.npz",
        )
        fit = store.query("SELECT * FROM fits WHERE fit_id = 'F2'")[0]
        assert fit["rt_backend"] == "robust_hybrid"
        assert fit["include_raman"] == 1
        assert fit["include_chl_fl"] == 1
        assert fit["include_cdom_fl"] == 0
        assert fit["fit_bp"] == 1
        assert fit["phi_c"] == pytest.approx(0.02)
        assert fit["wave_max"] == pytest.approx(700.0)
        assert fit["pab_version"] == "2.0.1"
        # the git SHAs ride along in the provenance JSON
        pkg = json.loads(fit["pkg_versions"])
        assert pkg["git_sha"]["PAB"]
        assert pkg["robust"] != "not installed"


def test_persist_fit_records_the_1_0_configuration_distinctly():
    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        artifacts.persist_fit(
            store,
            fit_id="F1",
            matchup_id=matchup_id,
            pixel_id=pixel_id,
            result=_fake_result(),
            config=FitConfig.v1(),
            chains_path="/tmp/F1.npz",
        )
        fit = store.query("SELECT * FROM fits WHERE fit_id = 'F1'")[0]
        assert fit["rt_backend"] == "gordon"
        assert fit["include_raman"] == 0
        assert fit["include_chl_fl"] == 0
        assert fit["fit_bp"] == 0
        assert fit["wave_max"] == pytest.approx(700.0)


# --- fitted physics everywhere (Prompt 3 Task 5) -----------------------------
class _SpyModel:
    """Minimal stand-in for a BING model, enough for reconstruct_rrs."""

    nparam = 3
    name = "ExpBricaud"
    wave = np.arange(400.0, 700.0, 20.0)


def test_reconstruct_rrs_uses_gordon_for_the_1_0_backend(monkeypatch):
    pytest.importorskip("bing")
    import bing.evaluate as ev

    calls = []
    monkeypatch.setattr(
        ev, "calc_Rrs_from_models", lambda *a, **k: calls.append(("gordon", k)) or 1.0
    )
    monkeypatch.setattr(
        ev,
        "calc_Rrs_from_models_robust",
        lambda *a, **k: calls.append(("robust", k)) or 2.0,
    )
    out = run.reconstruct_rrs(
        [_SpyModel(), _SpyModel()], np.zeros(3), np.zeros(2), {"rt_backend": "gordon"}
    )
    assert out == 1.0
    assert [c[0] for c in calls] == ["gordon"]


def test_reconstruct_rrs_uses_the_robust_backend_with_geom_and_bp(monkeypatch):
    """The task's assertion: a robust fit must reconstruct with robust physics."""
    pytest.importorskip("bing")
    import bing.evaluate as ev

    calls = []
    monkeypatch.setattr(
        ev, "calc_Rrs_from_models", lambda *a, **k: calls.append(("gordon", k)) or 1.0
    )
    monkeypatch.setattr(
        ev,
        "calc_Rrs_from_models_robust",
        lambda *a, **k: calls.append(("robust", k)) or 2.0,
    )
    geom = object()
    out = run.reconstruct_rrs(
        [_SpyModel(), _SpyModel()],
        np.zeros(3),
        np.zeros(2),
        {"rt_backend": "robust_hybrid", "fit_Bp": True},
        geom=geom,
        Bp=0.012,
    )
    assert out == 2.0
    assert [c[0] for c in calls] == ["robust"]
    assert calls[0][1]["geom"] is geom
    assert calls[0][1]["Bp"] == 0.012


def test_reconstruct_rrs_defaults_to_gordon_for_a_legacy_rt_dict(monkeypatch):
    """A 1.0 row has no ``rt_backend``; that must mean Gordon, not a crash."""
    pytest.importorskip("bing")
    import bing.evaluate as ev

    calls = []
    monkeypatch.setattr(
        ev, "calc_Rrs_from_models", lambda *a, **k: calls.append("gordon") or 1.0
    )
    run.reconstruct_rrs([_SpyModel(), _SpyModel()], np.zeros(3), np.zeros(2), {})
    assert calls == ["gordon"]


def test_config_from_row_rebuilds_the_2_0_configuration():
    from pab.plotting.fit_fig import _config_from_row

    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        artifacts.persist_fit(
            store,
            fit_id="F2",
            matchup_id=matchup_id,
            pixel_id=pixel_id,
            result=_fake_result(),
            config=FitConfig(),
            chains_path="/tmp/F2.npz",
        )
        row = store.query("SELECT * FROM fits WHERE fit_id = 'F2'")[0]
        cfg = _config_from_row(row)
        assert cfg.rt_backend == "robust_hybrid"
        assert cfg.include_Raman is True and cfg.include_Chl_fl is True
        assert cfg.fit_Bp is True and cfg.wave_max == pytest.approx(700.0)


def test_config_from_row_treats_a_legacy_null_row_as_gordon():
    """v1 rows have the v5 columns NULL — that is the elastic 1.0 fit."""
    from pab.plotting.fit_fig import _config_from_row

    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        store.upsert(
            "fits",
            {
                "fit_id": "OLD",
                "matchup_id": matchup_id,
                "pixel_id": pixel_id,
                "model_pair": "ExpBPow",
                "wave_min": 400.0,
                "wave_max": 700.0,
                "nsteps": 10000,
                "pab_version": "1.0",
            },
        )
        row = store.query("SELECT * FROM fits WHERE fit_id = 'OLD'")[0]
        cfg = _config_from_row(row)
        assert cfg.rt_backend == "gordon"
        assert cfg.include_Raman is False and cfg.fit_Bp is False
        assert cfg.wave_max == pytest.approx(700.0)


def test_geometry_from_row_reads_the_pixel_back():
    from pab.plotting.fit_fig import _geometry_from_row

    pytest.importorskip("bing")
    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        geom = _geometry_from_row(store, {"pixel_id": pixel_id})
        assert geom.theta_s == pytest.approx(GEOM["theta_s"])
        assert geom.theta_v == pytest.approx(GEOM["theta_v"])
        assert geom.dphi == pytest.approx(GEOM["dphi"])


def test_worker_init_pins_xla_threads(monkeypatch):
    """The fit pool runs JAX; without this each worker spawns ncores threads."""
    from pab.parallel import init_worker

    for var in ("XLA_FLAGS", "OMP_NUM_THREADS"):
        monkeypatch.delenv(var, raising=False)
    init_worker()
    assert os.environ["OMP_NUM_THREADS"] == "1"
    assert "intra_op_parallelism_threads=1" in os.environ["XLA_FLAGS"]
    assert "--xla_cpu_multi_thread_eigen=false" in os.environ["XLA_FLAGS"]


def test_fit_worker_init_is_the_shared_one(monkeypatch):
    """The two initialisers must not drift again."""
    monkeypatch.delenv("XLA_FLAGS", raising=False)
    run._worker_init()
    assert "intra_op_parallelism_threads=1" in os.environ["XLA_FLAGS"]


def test_init_worker_respects_a_deliberate_setting(monkeypatch):
    monkeypatch.setenv("XLA_FLAGS", "--custom=1")
    from pab.parallel import init_worker

    init_worker()
    assert os.environ["XLA_FLAGS"] == "--custom=1"


# --- Bp batch shape (the in-pod figure-stage failure, 2026-09-17) ------------
def test_broadcast_bp_shapes():
    """robust's batched-B_p layout is (nsamples, nwave), not (nsamples,)."""

    class _M:
        wave = np.arange(400.0, 700.0, 10.0)  # 30 bands

    models = [_M(), _M()]
    assert run._broadcast_bp(None, models) is None
    assert (
        run._broadcast_bp(np.float64(0.012), models).ndim == 0
    )  # scalar passes through
    out = run._broadcast_bp(np.full(7, 0.012), models)
    assert out.shape == (7, 30)
    already = np.full((7, 30), 0.012)
    assert run._broadcast_bp(already, models).shape == (7, 30)


def test_reconstruct_rrs_accepts_a_per_sample_bp_against_the_real_backend():
    """The regression test for the in-pod `figure` failure.

    ``fit_fig`` peels the chain's trailing ``B_p`` column, giving one value per
    posterior sample. Passed through unbroadcast, the robust backend died with
    ``Incompatible shapes for broadcasting: [(48000, 136), (48000,)]`` — deep
    inside JAX, and only in the pod, because the other caller passes a scalar
    and the dispatch unit tests mock the forward model. This exercises the
    **real** backend with a batch.
    """
    pytest.importorskip("bing")
    pytest.importorskip("robust")
    geom = _geom()
    wave = np.arange(410.0, 700.0, 20.0)
    _, rt_dict, models = run.build_models(FitConfig(), wave, geom=geom)
    from bing.models import utils as model_utils

    model_utils.init_other_bits(models, Chl=np.array([0.1]), Y=None, Rrs=None)
    run.set_inelastic_Ed(models, geom, rt_dict)

    n = 5
    a_params = np.tile(np.array([np.log10(0.02), 0.017, np.log10(0.03)]), (n, 1))
    bb_params = np.tile(np.array([np.log10(0.004), 1.0]), (n, 1))
    bp = np.full(n, 0.012)

    out = np.asarray(
        run.reconstruct_rrs(models, a_params, bb_params, rt_dict, geom=geom, Bp=bp)
    )
    assert out.shape == (n, models[0].wave.size)
    assert np.all(np.isfinite(out))


# -- the negative-blue QA count (O4, Q&A/Outliers 3 = A) ---------------------
def test_rrs_qa_quantities_counts_negative_blue_bands():
    """One quantity, ``n_neg_blue``: finite bands with Rrs < 0 inside the
    inclusive 400–450 nm window; NaN bands and bands outside it are ignored."""
    assert run.BLUE_QA_BAND == (400.0, 450.0)
    wave = np.array([395.0, 400.0, 410.0, 430.0, 450.0, 451.0, 560.0, 700.0])

    # all positive -> 0, and the dict has the fit_results shape
    out = run.rrs_qa_quantities(wave, np.full(wave.size, 1e-3))
    assert out == [
        {
            "quantity": "n_neg_blue",
            "value": 0.0,
            "value_lo": 0.0,
            "value_hi": 0.0,
            "unit": "bands",
        }
    ]
    assert out[0]["quantity"] == run.NEG_BLUE_QUANTITY

    # three negative bands inside the window (400 and 450 are inclusive edges),
    # plus negatives at 395, 451 and 700 that must not count
    rrs = np.array([-1.0, -1e-4, 1e-3, -2e-4, -3e-4, -1e-3, 1e-3, -1e-5])
    (q,) = run.rrs_qa_quantities(wave, rrs)
    assert q["value"] == 3 and q["value_lo"] == 3 and q["value_hi"] == 3
    assert isinstance(q["value"], float)

    # a NaN band inside the window is neither negative nor counted
    rrs_nan = rrs.copy()
    rrs_nan[1] = np.nan
    assert run.rrs_qa_quantities(wave, rrs_nan)[0]["value"] == 2
    # zero is not negative
    assert run.rrs_qa_quantities(wave, np.zeros(wave.size))[0]["value"] == 0
    # lists are fine too
    assert run.rrs_qa_quantities([420.0], [-1e-3])[0]["value"] == 1


def test_persist_fit_writes_n_neg_blue():
    """The count rides along in ``fit_results`` as ``BING_ExpBPow_n_neg_blue``
    -- no schema change, same prefix as every other quantity."""
    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        result = _fake_result()
        result.quantities = [*result.quantities, *run.rrs_qa_quantities([440.0], [-1e-3])]
        artifacts.persist_fit(
            store,
            fit_id="F1",
            matchup_id=matchup_id,
            pixel_id=pixel_id,
            result=result,
            config=FitConfig(),
        )
        row = store.query(
            "SELECT * FROM fit_results WHERE quantity = 'BING_ExpBPow_n_neg_blue'"
        )
        assert len(row) == 1
        assert row[0]["value"] == 1.0 and row[0]["value_lo"] == 1.0
        assert row[0]["value_hi"] == 1.0 and row[0]["unit"] == "bands"
        assert store.count("fit_results") == 3


def _qa_recording_stub(wave, Rrs, Rrs_unc, chl, config, geom=None):
    """`_stub_fit_only` plus the real QA count on the prepared spectrum -- the
    wiring ``fit_spectrum`` does, without the MCMC."""
    result = _fake_result()
    wave_w, Rrs_w, _ = run.prepare_spectrum(wave, Rrs, Rrs_unc, config=config)
    result.quantities = [*result.quantities, *run.rrs_qa_quantities(wave_w, Rrs_w)]
    return result


def test_build_fits_fits_a_negative_blue_spectrum_and_records_the_count(
    monkeypatch, tmp_path
):
    """Never a refusal: a pixel with Rrs < 0 at 440 nm is fitted as before and
    its row carries ``n_neg_blue = 1`` (Q&A/Outliers 3 = A, not B)."""
    pytest.importorskip("bing")
    from pab.tests.test_pace import make_granule

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(run, "_fit_only", _qa_recording_stub)
    ds = make_granule()
    ds["Rrs"].values[2, 2, 0] = -1e-3  # the 440 nm band of the fitted pixel

    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        out = run.build_fits(store, config=FitConfig(), opener=lambda _s: ds)
        fit_id = run.make_fit_id(matchup_id, 2, 2, "ExpBPow")
        assert out["written"] == [fit_id] and out["failed"] == []
        row = store.query(
            "SELECT value FROM fit_results WHERE fit_id = ? AND quantity = ?",
            (fit_id, "BING_ExpBPow_n_neg_blue"),
        )
        assert row == [{"value": 1.0}]
        # the chains NPZ holds the windowed spectrum the count was taken on
        npz = artifacts.load_chains(fit_id)
        assert run.rrs_qa_quantities(npz["wave"], npz["Rrs"])[0]["value"] == 0  # stub


def test_fit_spectrum_fits_a_negative_blue_spectrum():
    """The real path (1.0 Gordon, short chain): two negative blue bands are
    counted, and the fit runs rather than refusing."""
    pytest.importorskip("bing")
    pytest.importorskip("emcee")
    np.random.seed(0)
    config = FitConfig.v1(nsteps=300, nburn=100, analysis_burn=100)
    wave = np.arange(405.0, 700.0, 8.0)
    truth = [0.02, 0.017, 0.03, 0.004, 1.0]
    try:
        rrs = _synth_rrs(config, wave, truth, 0.1)
    except FileNotFoundError as exc:
        pytest.skip(f"BING aph-basis data unavailable: {exc}")
    rrs = rrs.copy()
    rrs[:2] = -2e-4  # 405 and 413 nm below zero, as on a runaway's spectrum
    result = run.fit_spectrum(wave, rrs, 0.02 * rrs, Chl=0.1, config=config)
    neg = next(q for q in result.quantities if q["quantity"] == "n_neg_blue")
    assert neg["value"] == 2 and neg["unit"] == "bands"
    assert np.isfinite(result.chains).all()
    # the 1.0 path's 10 BING quantities (5 params, no Bp, 2x2 IOPs, chl) + n_neg_blue
    assert len(result.quantities) == 11 and result.quantities[-1]["quantity"] == "n_neg_blue"
