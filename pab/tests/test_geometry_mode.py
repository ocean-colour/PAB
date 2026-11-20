"""2.1: the normalized-geometry fit (``FitConfig.geometry_mode``, schema v6).

``claude_prompts/v2/build_v2_1_rerun.md`` Plan §2 h. The PACE L2 AOP ``Rrs``
is normalized to (θ_s, θ_v, Δφ) = (0, 0, 0) (l2gen ``brdf_opt = 7``), so the
2.1 forward model runs there — and the inelastic ``Ed`` at θ_s = 0 — whatever
the pixel's L1B angles are. These tests pin the resolver, every consumer of
it (fit, ``Ed``, diagnostics, figure reconstruction), the R3 split, the v6
migration and the frozen constructors.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from pab.db import Store, schema
from pab.fit import FitConfig, artifacts, run
from pab.fit.models import GEOM_NORMALIZED, GEOM_OBSERVED
from pab.tests.test_fit import GEOM, _fake_result, _seed_matchup

ANGLES = (GEOM["theta_s"], GEOM["theta_v"], GEOM["dphi"])


def _angles(geom):
    return (geom.theta_s, geom.theta_v, geom.dphi)


# --- the frozen constructors --------------------------------------------------
def test_default_is_2_1_normalized():
    assert FitConfig().geometry_mode == GEOM_NORMALIZED


def test_frozen_constructors_pin_observed_geometry():
    c201 = FitConfig.v2_0_1()
    assert c201.geometry_mode == GEOM_OBSERVED
    # 2.0.1 differs from the 2.1 default in the geometry and nothing else
    assert c201 == FitConfig(geometry_mode=GEOM_OBSERVED)
    c20 = FitConfig.v2_0()
    assert c20.geometry_mode == GEOM_OBSERVED
    assert (c20.bbp600_max, c20.adg_max, c20.aph_max) == (None, None, None)
    assert FitConfig.v1().geometry_mode == GEOM_OBSERVED
    assert FitConfig.v2_0_1(nsteps=5).nsteps == 5


def test_unknown_geometry_mode_is_refused():
    with pytest.raises(ValueError, match="geometry_mode"):
        FitConfig(geometry_mode="nadir")


# --- the resolver -------------------------------------------------------------
def test_fit_geometry_normalized_is_zero_whatever_the_pixel():
    pytest.importorskip("bing")
    for angles in (ANGLES, (None, None, None), (75.0, 60.0, -170.0)):
        geom = run.fit_geometry(FitConfig(), *angles)
        assert _angles(geom) == (0.0, 0.0, 0.0)


def test_fit_geometry_observed_passes_the_pixel_through():
    pytest.importorskip("bing")
    geom = run.fit_geometry(FitConfig.v2_0_1(), *ANGLES)
    assert _angles(geom) == pytest.approx(ANGLES)
    assert run.fit_geometry(FitConfig.v2_0_1(), None, None, None) is None


def test_fit_geometry_is_none_for_gordon():
    assert run.fit_geometry(FitConfig.v1(), *ANGLES) is None


def test_requires_pixel_angles_splits_from_requires_geometry():
    assert run.requires_geometry(FitConfig()) is True
    assert run.requires_pixel_angles(FitConfig()) is False  # V5
    assert run.requires_pixel_angles(FitConfig.v2_0_1()) is True
    assert run.requires_pixel_angles(FitConfig.v2_0()) is True
    assert run.requires_pixel_angles(FitConfig.v1()) is False


def test_normalized_fit_refuses_an_observed_geometry():
    """Handing observed angles to a normalized fit is a caller bug, not a
    request to override — it raises before any model is built."""
    obs = pytest.importorskip("bing.rt.geometry").ObsGeometry(*ANGLES)
    wave = np.arange(405.0, 715.0, 10.0)
    rrs = np.full(wave.size, 0.003)
    with pytest.raises(ValueError, match="normalized"):
        run.fit_spectrum(wave, rrs, 0.02 * rrs, Chl=0.1, geom=obs,
                         config=FitConfig(nsteps=10))


# --- the consumers ------------------------------------------------------------
class _Stop(Exception):
    pass


def test_fit_spectrum_wires_zero_geometry_into_models_and_Ed(monkeypatch):
    """``geom=None`` under normalized → (0, 0, 0) reaches ``build_models`` and
    ``set_inelastic_Ed`` (stopped there: no MCMC needed)."""
    pytest.importorskip("bing")
    seen = {}
    real_build = run.build_models

    def _build(config, wave, *, geom=None, validate=True):
        seen["build"] = _angles(geom)
        return real_build(config, wave, geom=geom, validate=validate)

    def _ed(models, geom, rt_dict):
        seen["ed"] = _angles(geom)
        raise _Stop

    monkeypatch.setattr(run, "build_models", _build)
    monkeypatch.setattr(run, "set_inelastic_Ed", _ed)
    wave = np.arange(405.0, 715.0, 10.0)
    rrs = np.full(wave.size, 0.003)
    with pytest.raises(_Stop):
        run.fit_spectrum(wave, rrs, 0.02 * rrs, Chl=0.1, config=FitConfig(nsteps=10))
    assert seen == {"build": (0.0, 0.0, 0.0), "ed": (0.0, 0.0, 0.0)}


def test_inelastic_Ed_is_taken_at_zero_solar_zenith(monkeypatch):
    pytest.importorskip("bing")
    ed_mod = pytest.importorskip("robust.rt.ed")
    calls = []
    real = ed_mod.Ed

    def _rec(theta_s, wave):
        calls.append(float(theta_s))
        return real(theta_s, wave)

    monkeypatch.setattr(ed_mod, "Ed", _rec)
    wave = np.arange(405.0, 715.0, 10.0)
    geom = run.fit_geometry(FitConfig(), *ANGLES)
    _, rt_dict, models = run.build_models(FitConfig(), wave, geom=geom)
    assert run.set_inelastic_Ed(models, geom, rt_dict) is True
    assert calls == [0.0]


def test_diagnostics_use_the_fit_geometry(monkeypatch):
    """χ²/AIC/BIC are scored at the geometry the fit ran at."""
    pytest.importorskip("bing")
    seen = []

    def _rrs(models, a, bb, rt_dict, *, geom=None, Bp=None):
        seen.append(_angles(geom))
        return np.zeros(models[0].wave.size)

    monkeypatch.setattr(run, "reconstruct_rrs", _rrs)
    wave = np.arange(405.0, 715.0, 10.0)
    geom = run.fit_geometry(FitConfig(), *ANGLES)
    _, rt_dict, models = run.build_models(FitConfig(), wave, geom=geom)
    chains = np.tile([-1.7, 0.017, -1.5, -2.4, 1.0, 0.012], (20, 4, 1))
    run._fit_diagnostics(models, chains, rt_dict, np.full(wave.size, 1e-3),
                         np.full(wave.size, 1e-8), FitConfig(), geom=geom)
    assert seen == [(0.0, 0.0, 0.0)]


def _recording_fit_only(log):
    def _fit_only(wave, Rrs, Rrs_unc, chl, config, geom=None):
        log.append(None if geom is None else _angles(geom))
        return _fake_result()

    return _fit_only


def test_build_fits_normalized_fits_a_pixel_without_angles(monkeypatch, tmp_path):
    """V5: under normalized a NULL-angle pixel is fitted, at (0, 0, 0)."""
    pytest.importorskip("bing")
    from pab.tests.test_pace import make_granule

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    log = []
    monkeypatch.setattr(run, "_fit_only", _recording_fit_only(log))
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store, geometry=False)
        out = run.build_fits(store, config=FitConfig(), opener=lambda _s: make_granule())
        assert out["failed"] == []
        assert out["written"] == [run.make_fit_id(matchup_id, 2, 2, "ExpBPow")]
        row = store.query("SELECT geom_mode FROM fits")[0]
        assert row["geom_mode"] == GEOM_NORMALIZED
    assert log == [(0.0, 0.0, 0.0)]


def test_build_fits_normalized_ignores_the_stored_angles(monkeypatch, tmp_path):
    pytest.importorskip("bing")
    from pab.tests.test_pace import make_granule

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    log = []
    monkeypatch.setattr(run, "_fit_only", _recording_fit_only(log))
    with Store.open(":memory:") as store:
        _seed_matchup(store)  # angles present
        run.build_fits(store, config=FitConfig(), opener=lambda _s: make_granule())
        run.build_fits(store, config=FitConfig.v2_0_1(), opener=lambda _s: make_granule(),
                       replace=True)
    assert log[0] == (0.0, 0.0, 0.0)
    assert log[1] == pytest.approx(ANGLES)


def test_fit_matchup_normalized_without_angles_is_not_refused(monkeypatch, tmp_path):
    pytest.importorskip("bing")
    from pab.tests.test_pace import make_granule

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    log = []
    monkeypatch.setattr(run, "_fit_only", _recording_fit_only(log))
    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store, geometry=False)
        run.fit_matchup(store, matchup_id, config=FitConfig(),
                        opener=lambda _s: make_granule())
    assert log == [(0.0, 0.0, 0.0)]


# --- provenance: schema v6 ----------------------------------------------------
def _v5_shaped_db(path):
    """A v5-shaped ``fits`` table holding a 2.0 row, stamped user_version 5."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE fits (fit_id TEXT PRIMARY KEY, algorithm TEXT, "
        "pab_version TEXT, rt_backend TEXT)"
    )
    conn.execute(
        "INSERT INTO fits VALUES ('F20', 'BING', '2.0', 'robust_hybrid')"
    )
    conn.execute("PRAGMA user_version = 5")
    conn.commit()
    return conn


def test_v5_to_v6_adds_geom_mode_null_on_legacy_rows(tmp_path):
    conn = _v5_shaped_db(tmp_path / "v5.db")
    before = conn.execute("SELECT * FROM fits").fetchall()
    schema.migrate(conn)
    assert schema.get_version(conn) == schema.SCHEMA_VERSION == 6
    row = conn.execute(
        "SELECT fit_id, algorithm, pab_version, rt_backend, geom_mode FROM fits"
    ).fetchone()
    assert row == (*before[0], None)
    schema.migrate(conn)  # idempotent
    cols = [r[1] for r in conn.execute("PRAGMA table_info(fits)")]
    assert cols.count("geom_mode") == 1
    conn.close()


def test_persist_fit_stamps_geom_mode():
    with Store.open(":memory:") as store:
        matchup_id, pixel_id = _seed_matchup(store)
        for fit_id, cfg in (("N", FitConfig()), ("O", FitConfig.v2_0_1())):
            artifacts.persist_fit(
                store, fit_id=fit_id, matchup_id=matchup_id, pixel_id=pixel_id,
                result=_fake_result(), config=cfg, chains_path="/tmp/x.npz",
            )
        rows = {r["fit_id"]: r["geom_mode"] for r in store.query("SELECT * FROM fits")}
    assert rows == {"N": GEOM_NORMALIZED, "O": GEOM_OBSERVED}


# --- reconstruction -----------------------------------------------------------
def _robust_row(store, fit_id, matchup_id, pixel_id, geom_mode):
    store.upsert(
        "fits",
        {
            "fit_id": fit_id, "matchup_id": matchup_id, "pixel_id": pixel_id,
            "algorithm": "BING", "model_pair": "ExpBPow",
            "wave_min": 400.0, "wave_max": 700.0, "nsteps": 20,
            "pab_version": "x", "rt_backend": "robust_hybrid",
            "include_raman": 1, "include_chl_fl": 1, "include_cdom_fl": 0,
            "phi_c": 0.02, "fit_bp": 1, "geom_mode": geom_mode,
        },
    )
    return store.query("SELECT * FROM fits WHERE fit_id = ?", (fit_id,))[0]


def test_config_from_row_reads_geom_mode_and_null_is_observed():
    from pab.plotting.fit_fig import _config_from_row

    with Store.open(":memory:") as store:
        m, px = _seed_matchup(store)
        assert _config_from_row(_robust_row(store, "A", m, px, "normalized")) \
            .geometry_mode == GEOM_NORMALIZED
        assert _config_from_row(_robust_row(store, "B", m, px, "observed")) \
            .geometry_mode == GEOM_OBSERVED
        assert _config_from_row(_robust_row(store, "C", m, px, None)) \
            .geometry_mode == GEOM_OBSERVED


def test_geometry_from_row_dispatches_on_geom_mode():
    pytest.importorskip("bing")
    from pab.plotting.fit_fig import _geometry_from_row

    with Store.open(":memory:") as store:
        m, px = _seed_matchup(store)  # the pixel has real angles
        g21 = _geometry_from_row(store, _robust_row(store, "A", m, px, "normalized"))
        g20 = _geometry_from_row(store, _robust_row(store, "C", m, px, None))
    assert _angles(g21) == (0.0, 0.0, 0.0)
    assert _angles(g20) == pytest.approx(ANGLES)


@pytest.mark.parametrize("geom_mode, expected", [
    ("normalized", (0.0, 0.0, 0.0)), (None, ANGLES), ("observed", ANGLES),
])
def test_reconstruct_fit_runs_at_the_row_geometry(monkeypatch, tmp_path, geom_mode,
                                                   expected):
    """A 2.1 figure is drawn at (0, 0, 0); a 2.0 one at its observed angles."""
    pytest.importorskip("bing")
    from pab.plotting import fit_fig

    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path)
    seen = {}

    def _rrs(models, a, bb, rt_dict, *, geom=None, Bp=None):
        seen["rrs"] = _angles(geom)
        return np.zeros((a.shape[0], models[0].wave.size))

    def _ed(models, geom, rt_dict):
        seen["ed"] = _angles(geom)
        return True

    monkeypatch.setattr(run, "reconstruct_rrs", _rrs)
    monkeypatch.setattr(run, "set_inelastic_Ed", _ed)
    res = _fake_result()
    res.wave = np.arange(405.0, 705.0, 10.0)
    res.Rrs = np.full(res.wave.size, 2e-3)
    res.varRrs = np.full(res.wave.size, 1e-9)
    res.chains = np.tile([-1.7, 0.017, -1.5, -2.4, 1.0, 0.012], (20, 4, 1))
    res.param_names = ["Adg", "Sdg", "Aph", "Bnw", "beta", "Bp"]
    with Store.open(":memory:") as store:
        m, px = _seed_matchup(store)
        _robust_row(store, "F", m, px, geom_mode)
        artifacts.save_chains("F", res)
        out = fit_fig.reconstruct_fit(store, "F")
    assert len(out) == 8
    assert seen["rrs"] == pytest.approx(expected)
    assert seen["ed"] == pytest.approx(expected)


# --- the report headline ------------------------------------------------------
def test_version_family_makes_2_1_the_headline_base():
    from pab.metrics import compare
    from pab.tests.test_compare_versions import _add_bing_fit

    assert not compare.is_patch_version("2.1")
    with Store.open(":memory:") as store:
        m, px = _seed_matchup(store)
        _add_bing_fit(store, m, px, version="2.0", bbp=5e4)
        _add_bing_fit(store, m, px, version="2.0.1", bbp=4e-4)
        _add_bing_fit(store, m, px, version="2.1", bbp=5e-4)
        assert compare.version_family(store) == ("2.1", [])
        assert compare.resolve_versions(store) == ["2.1"]
        # the earlier family is still reachable explicitly
        assert compare.version_family(store, "2.0.1") == ("2.0", ["2.0.1"])
        df = compare.gather_matchups(store)
        assert list(df["fit_id"]) == [f"{m}_{px}_ExpBPow_v2.1"]
        assert list(df["pab_version"]) == ["2.1"]
        assert compare.fit_version_counts(store) == {"2.1": 1}


def test_1_0_vs_2_1_pair_and_labels(tmp_path):
    from pab.metrics import compare
    from pab.report import rst
    from pab.tests.test_compare_versions import _add_bing_fit

    v1 = tmp_path / "v1.db"
    with Store.open(str(v1)) as s1:
        m, px = _seed_matchup(s1)
        _add_bing_fit(s1, m, px, version="1.0", bbp=2e-3)
    with Store.open(":memory:") as store:
        m, px = _seed_matchup(store)
        _add_bing_fit(store, m, px, version="2.0", bbp=1e-3)
        _add_bing_fit(store, m, px, version="2.1", bbp=1.1e-3)
        df = compare.gather_version_pair(store, str(v1))
        assert list(df["version_v2"]) == ["2.1"]
        assert rst._v2_label(df) == "2.1"
        page = rst.version_section(store, str(v1), sortable=False)
    assert "1.0 vs 2.1" in page and "median 2.1/1.0 ratio" in page
    assert "1.0 vs 2.0" not in page


# --- a real toy fit at the normalized geometry --------------------------------
def test_robust_toy_fit_at_normalized_geometry_recovers_bbp():
    pytest.importorskip("bing")
    pytest.importorskip("emcee")
    pytest.importorskip("robust")
    from pab.tests.test_fit import _synth_rrs_robust

    np.random.seed(1)
    config = FitConfig(nsteps=1000, nburn=300, analysis_burn=300)
    wave = np.arange(405.0, 715.0, 10.0)
    truth = [0.02, 0.017, 0.03, 0.004, 1.0]
    try:
        rrs = _synth_rrs_robust(config, wave, truth, 0.1, run.normalized_geometry(),
                                0.012)
        result = run.fit_spectrum(wave, rrs, 0.02 * rrs, Chl=0.1, config=config)
    except FileNotFoundError as exc:
        pytest.skip(f"BING aph-basis data unavailable: {exc}")
    bbp700 = next(q for q in result.quantities if q["quantity"] == "bbp700")
    assert bbp700["value"] == pytest.approx(0.004 * (600.0 / 700.0), rel=0.5)
    assert np.isfinite(result.chisq)
